import aiosqlite
import sqlite_vec
import structlog
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from aura.config import get_config

logger = structlog.get_logger(__name__)


async def load_extensions(db: aiosqlite.Connection) -> None:
    """
    Loads required SQLite extensions, specifically sqlite-vec for vector operations.
    """
    try:
        await db.enable_load_extension(True)
        # sqlite_vec.loadable_path() returns the path to the compiled extension
        await db.load_extension(sqlite_vec.loadable_path())
        await db.enable_load_extension(False)
        logger.debug("Successfully loaded sqlite-vec extension")
    except Exception as e:
        logger.error("Failed to load sqlite-vec extension", error=str(e))
        raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager that provides a connection to the RAG database
    with necessary extensions loaded and foreign keys enabled.
    """
    config = get_config()
    db_path = config.rag_db_path

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await load_extensions(db)
        yield db


async def init_db() -> None:
    """
    Initializes the database schema using a simple migration system.
    Runs CREATE TABLE IF NOT EXISTS on startup for all required tables.
    """
    logger.info("Initializing RAG database", path=str(get_config().rag_db_path))

    async with get_db() as db:
        # Table for tracking ingested documents
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for storing text chunks and their embeddings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        # FTS5 virtual table for keyword search on chunk content
        # content=chunks allows the virtual table to use the chunks table as the source
        # however, it's often easier to just store the content in both or manage triggers.
        # For simplicity and following the prompt's "three tables" instruction:
        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                content,
                chunk_id UNINDEXED,
                tokenize='unicode61'
            )
        """)

        await db.commit()
        logger.info("RAG database initialization complete")
