import hashlib
from pathlib import Path
from typing import List

import structlog

from aura.config import get_config
from aura.ollama.client import OllamaClient
from aura.rag.db import get_db
from aura.rag.ingestor import get_parser

logger = structlog.get_logger(__name__)


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """
    Splits text into overlapping chunks of a specified size.
    Simple character-based splitting as a baseline.
    """
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

        # Prevent infinite loop if overlap >= chunk_size
        if overlap >= chunk_size:
            break

    return chunks


async def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """
    Generates embedding vectors for a list of text chunks using Ollama.
    """
    config = get_config()
    client = OllamaClient()
    embeddings = []

    for chunk in chunks:
        # We process one by one because the current embed method in OllamaClient
        # only takes a single string and returns one embedding.
        try:
            vector = await client.embed(config.embed_model, chunk)
            embeddings.append(vector)
        except Exception as e:
            logger.error(
                "chunk_embedding_failed", error=str(e), chunk_preview=chunk[:50]
            )
            # If embedding fails, we still want to maintain list index alignment
            # Or we could raise. For RAG, missing a chunk is better than crashing ingestion?
            # Actually, alignment is critical if we store them later.
            embeddings.append([])

    return embeddings


def calculate_sha256(file_path: Path) -> str:
    """
    Calculates the SHA256 hash of a file.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


async def ingest_file(file_path: Path) -> bool:
    """
    Coordinates the ingestion pipeline for a single file:
    1. Check for duplicates using SHA256.
    2. Extract text using the appropriate parser.
    3. Chunk the text.
    4. Generate embeddings for chunks.
    5. Store metadata and chunks in the database.
    """
    logger.info("ingesting_file", path=str(file_path))

    if not file_path.exists():
        logger.error("ingestion_failed_file_not_found", path=str(file_path))
        return False

    # 1. Deduplication check
    file_hash = calculate_sha256(file_path)
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM documents WHERE hash = ?", (file_hash,)
        )
        if await cursor.fetchone():
            logger.info("ingestion_skipped_duplicate", path=str(file_path))
            return True

        # 2. Parse text
        parser = get_parser(file_path)
        if not parser:
            logger.warning("ingestion_skipped_unsupported_format", path=str(file_path))
            return False

        try:
            text = parser.extract_text(file_path)
        except Exception as e:
            logger.error(
                "ingestion_failed_parsing_error", path=str(file_path), error=str(e)
            )
            return False

        if not text:
            logger.warning("ingestion_skipped_empty_file", path=str(file_path))
            return False

        # 3. Chunking
        chunks = chunk_text(text)

        # 4. Embedding
        embeddings = await embed_chunks(chunks)

        # Filter out failed embeddings and their corresponding chunks
        # Alignment is important: len(chunks) == len(embeddings)
        valid_chunks_and_embeddings = [(c, e) for c, e in zip(chunks, embeddings) if e]

        if not valid_chunks_and_embeddings:
            logger.error("ingestion_failed_no_valid_embeddings", path=str(file_path))
            return False

        # 5. Database storage
        try:
            # Insert document metadata
            cursor = await db.execute(
                "INSERT INTO documents (path, hash) VALUES (?, ?)",
                (str(file_path), file_hash),
            )
            doc_id = cursor.lastrowid

            # Insert chunks and embeddings
            for content, vector in valid_chunks_and_embeddings:
                # Store vector as BLOB (using json.dumps for now as a simple way to store floats in a BLOB)
                # sqlite-vec expects a BLOB of floats.
                # Actually, sqlite-vec can use float32 BLOBs.
                # The documentation for sqlite-vec says we can use vec_f32() in SQL
                # but for storing we need a packed float array.
                import struct

                blob_vector = struct.pack(f"{len(vector)}f", *vector)

                chunk_cursor = await db.execute(
                    "INSERT INTO chunks (document_id, content, embedding) VALUES (?, ?, ?)",
                    (doc_id, content, blob_vector),
                )
                chunk_id = chunk_cursor.lastrowid

                # Insert into FTS virtual table
                await db.execute(
                    "INSERT INTO fts_chunks (content, chunk_id) VALUES (?, ?)",
                    (content, chunk_id),
                )

            await db.commit()
            logger.info(
                "ingestion_complete",
                path=str(file_path),
                chunks=len(valid_chunks_and_embeddings),
            )
            return True

        except Exception as e:
            logger.error("ingestion_failed_db_error", path=str(file_path), error=str(e))
            await db.rollback()
            return False
