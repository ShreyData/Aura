import struct
from typing import Any, Dict, List

import structlog

from aura.config import get_config
from aura.ollama.client import OllamaClient
from aura.rag.db import get_db

logger = structlog.get_logger(__name__)


async def semantic_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Performs semantic search using sqlite-vec cosine similarity.
    Returns a list of chunks with their content, metadata, and distance.
    """
    config = get_config()
    client = OllamaClient()

    try:
        # 1. Generate embedding for the query
        query_vector = await client.embed(config.embed_model, query)
        if not query_vector:
            return []

        # 2. Pack vector into float32 BLOB for sqlite-vec
        query_blob = struct.pack(f"{len(query_vector)}f", *query_vector)

        # 3. Query the database
        async with get_db() as db:
            # vec_distance_cosine returns a value between 0 and 2.
            # 0 is identical, 2 is opposite.
            async with db.execute(
                """
                SELECT 
                    c.id,
                    c.content, 
                    d.path, 
                    vec_distance_cosine(c.embedding, ?) as distance
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY distance ASC
                LIMIT ?
                """,
                (query_blob, top_k),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row["id"],
                        "content": row["content"],
                        "path": row["path"],
                        "score": 1.0
                        - (row["distance"] / 2.0),  # Normalize to 0-1 similarity
                        "type": "semantic",
                    }
                    for row in rows
                ]

    except Exception as e:
        logger.error("semantic_search_failed", error=str(e), query=query)
        return []


async def keyword_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Performs keyword search using SQLite FTS5 with BM25 ranking.
    """
    try:
        async with get_db() as db:
            # BM25: smaller value is better match
            async with db.execute(
                """
                SELECT 
                    c.id,
                    c.content, 
                    d.path, 
                    bm25(fts_chunks) as rank
                FROM fts_chunks
                JOIN chunks c ON fts_chunks.chunk_id = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE fts_chunks MATCH ?
                ORDER BY rank ASC
                LIMIT ?
                """,
                (query, top_k),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row["id"],
                        "content": row["content"],
                        "path": row["path"],
                        "score": -row["rank"],  # Higher is better for unified scoring
                        "type": "keyword",
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error("keyword_search_failed", error=str(e), query=query)
        return []


async def hybrid_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Combines semantic and keyword search results using Reciprocal Rank Fusion (RRF).
    This is the primary method to be called from the chat system.
    """
    logger.debug("hybrid_search_start", query=query, top_k=top_k)

    # 1. Run both searches in parallel
    import asyncio

    semantic_results, keyword_results = await asyncio.gather(
        semantic_search(query, top_k=top_k * 2), keyword_search(query, top_k=top_k * 2)
    )

    # 2. Apply Reciprocal Rank Fusion
    # RRF score = sum(1 / (k + rank))
    # k is a constant, typically 60
    k = 60
    scores: Dict[int, float] = {}
    chunk_data: Dict[int, Dict[str, Any]] = {}

    # Helper to process result lists
    def process_results(results: List[Dict[str, Any]]):
        for rank, res in enumerate(results, start=1):
            chunk_id = res["id"]
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
                chunk_data[chunk_id] = res
            scores[chunk_id] += 1.0 / (k + rank)

    process_results(semantic_results)
    process_results(keyword_results)

    # 3. Sort by RRF score and take top_k
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]

    final_results = []
    for cid in sorted_ids:
        data = chunk_data[cid]
        data["rrf_score"] = scores[cid]
        final_results.append(data)

    logger.info("hybrid_search_complete", query=query, result_count=len(final_results))
    return final_results
