import base64
import os
from typing import Any, Dict, List, Optional

import aiosqlite
import keyring
import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aura.config import get_config

logger = structlog.get_logger(__name__)

# Constants for keyring
SERVICE_NAME = "aura-ai"
KEY_USERNAME = "history-key"


def get_or_create_key() -> bytes:
    """
    Retrieves the encryption key from the OS keychain or generates a new one.
    """
    key_hex = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
    if key_hex:
        try:
            return bytes.fromhex(key_hex)
        except ValueError:
            logger.error("invalid_key_format_in_keychain")

    # Generate new 32-byte key
    key = os.urandom(32)
    keyring.set_password(SERVICE_NAME, KEY_USERNAME, key.hex())
    logger.info("generated_new_history_encryption_key")
    return key


class Encryptor:
    """
    Handles AES-256-GCM encryption and decryption.
    """

    def __init__(self, key: bytes):
        self.aesgcm = AESGCM(key)

    def encrypt(self, data: str) -> str:
        """
        Encrypts a string and returns a base64 encoded string containing nonce + ciphertext.
        """
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data.encode(), None)
        # Store as base64(nonce + ciphertext)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypts a base64 encoded string (nonce + ciphertext).
        """
        raw_data = base64.b64decode(encrypted_data)
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        decrypted_data = self.aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_data.decode()


_encryptor: Optional[Encryptor] = None


def get_encryptor() -> Encryptor:
    global _encryptor
    if _encryptor is None:
        key = get_or_create_key()
        _encryptor = Encryptor(key)
    return _encryptor


async def get_db():
    config = get_config()
    db_path = config.history_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    return db


async def init_history_db():
    """
    Initializes the history database schema.
    """
    async with await get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        await db.commit()
    logger.info("history_database_initialized")


async def save_message(
    session_id: str, role: str, content: str, title: Optional[str] = None
):
    """
    Saves an encrypted message to the database. Creates a session if it doesn't exist.
    """
    encryptor = get_encryptor()
    encrypted_content = encryptor.encrypt(content)

    async with await get_db() as db:
        # Ensure session exists
        cursor = await db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not await cursor.fetchone():
            await db.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title or "New Chat"),
            )
        else:
            await db.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )

        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, encrypted_content),
        )
        await db.commit()


async def get_session(session_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves and decrypts all messages for a given session.
    """
    encryptor = get_encryptor()
    messages = []

    async with await get_db() as db:
        async with db.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ) as cursor:
            async for row in cursor:
                try:
                    decrypted_content = encryptor.decrypt(row["content"])
                    messages.append(
                        {
                            "role": row["role"],
                            "content": decrypted_content,
                            "created_at": row["created_at"],
                        }
                    )
                except Exception as e:
                    logger.error(
                        "message_decryption_failed", session_id=session_id, error=str(e)
                    )

    return messages


async def list_sessions() -> List[Dict[str, Any]]:
    """
    Lists all chat sessions.
    """
    async with await get_db() as db:
        async with db.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_session(session_id: str):
    """
    Deletes a session and all its messages.
    """
    async with await get_db() as db:
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
    logger.info("session_deleted", session_id=session_id)
