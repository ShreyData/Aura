from pathlib import Path
from typing import List

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from aura.api.schemas import (
    RAGDocument,
    RAGIngestRequest,
    RAGQueryRequest,
    RAGSearchResult,
)
from aura.rag.db import get_db
from aura.rag.embedder import ingest_file
from aura.rag.retriever import hybrid_search

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/rag", tags=["RAG"])


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_rag_file(request: RAGIngestRequest, background_tasks: BackgroundTasks):
    """
    Ingest a file into the RAG system. Runs as a background task.
    """
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.path}",
        )

    background_tasks.add_task(ingest_file, path)
    return {"status": "accepted", "message": f"Ingestion of {request.path} started."}


@router.get("/documents", response_model=List[RAGDocument])
async def list_rag_documents():
    """
    List all ingested documents.
    """
    async with get_db() as db:
        async with db.execute(
            "SELECT id, path, hash, created_at FROM documents ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [RAGDocument(**dict(row)) for row in rows]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_document(document_id: int):
    """
    Remove a document and all its chunks from the RAG system.
    """
    async with get_db() as db:
        # Check if exists
        cursor = await db.execute(
            "SELECT id FROM documents WHERE id = ?", (document_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # Deleting from documents will cascade to chunks due to ON DELETE CASCADE
        await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))

        # FTS table doesn't support CASCADE automatically in our setup if not using triggers.
        # Let's clean up FTS table as well.
        # We need to find chunk_ids before deleting chunks, or use a trigger.
        # For simplicity, we can delete based on content if it's unique enough, but better to use chunk_ids.
        # Since chunks are already gone (if cascaded), we should have handled this.
        # Let's do it manually to be safe before chunks are gone or by joining.
        await db.execute(
            """
            DELETE FROM fts_chunks 
            WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = ?)
            """,
            (document_id,),
        )

        await db.commit()
    return


@router.post("/query", response_model=List[RAGSearchResult])
async def query_rag(request: RAGQueryRequest):
    """
    Run hybrid search on the RAG system.
    """
    results = await hybrid_search(request.query, top_k=request.top_k)
    return [RAGSearchResult(**res) for res in results]
