import asyncio
import uuid
from typing import Any, Dict, List, Optional

import structlog

from aura.api.schemas import PendingToolCall
from aura.events import get_event_bus
from aura.tools.base import RiskLevel

logger = structlog.get_logger()


class ApprovalGate:
    """
    Manages the lifecycle of tool calls that require explicit user approval.
    Ensures that high-risk operations are gated by human-in-the-loop confirmation.
    """

    def __init__(self) -> None:
        # Maps request_id -> (asyncio.Event, approval_status, PendingToolCall)
        self._pending: Dict[str, tuple[asyncio.Event, bool, PendingToolCall]] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._event_bus = get_event_bus()

    async def _get_lock(self) -> asyncio.Lock:
        """Lazy initialization of the lock to ensure it binds to the current loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def request_approval(
        self, tool_name: str, args: Dict[str, Any], risk_level: RiskLevel
    ) -> bool:
        """
        Creates a pending approval request and waits for a response or timeout.
        Returns True if approved, False otherwise.
        """
        request_id = str(uuid.uuid4())
        event = asyncio.Event()
        
        pending_call = PendingToolCall(
            request_id=request_id,
            tool_name=tool_name,
            args=args,
            risk_level=risk_level.value,
        )

        lock = await self._get_lock()
        async with lock:
            # Status defaults to False (denied) until explicitly approved
            self._pending[request_id] = (event, False, pending_call)

        logger.info(
            "tool_approval_requested",
            request_id=request_id,
            tool_name=tool_name,
            risk_level=risk_level.value,
        )

        # Notify the UI via the event bus (which forwards to WebSocket)
        await self._event_bus.publish("tool_approval_needed", pending_call.model_dump())

        try:
            # Wait for 60 seconds for a response
            await asyncio.wait_for(event.wait(), timeout=60.0)
            
            async with lock:
                _, approved, _ = self._pending.get(request_id, (None, False, None))
                return approved

        except asyncio.TimeoutError:
            logger.warning("tool_approval_timeout", request_id=request_id, tool_name=tool_name)
            return False
        finally:
            # Always clean up the pending request
            async with lock:
                self._pending.pop(request_id, None)

    async def respond(self, request_id: str, approved: bool) -> bool:
        """
        Processes a response from the user/UI for a specific request ID.
        Returns True if the request was found and updated, False otherwise.
        """
        lock = await self._get_lock()
        async with lock:
            if request_id not in self._pending:
                logger.warning("tool_approval_response_invalid_id", request_id=request_id)
                return False

            event, _, pending_call = self._pending[request_id]
            self._pending[request_id] = (event, approved, pending_call)
            
            logger.info(
                "tool_approval_responded",
                request_id=request_id,
                approved=approved,
                tool_name=pending_call.tool_name,
            )
            
            event.set()
            return True

    async def get_pending(self) -> List[PendingToolCall]:
        """
        Returns a list of all tool calls currently awaiting approval.
        """
        lock = await self._get_lock()
        async with lock:
            return [data[2] for data in self._pending.values()]


# Singleton instance
_gate: Optional[ApprovalGate] = None


def get_approval_gate() -> ApprovalGate:
    """
    Returns the global ApprovalGate singleton.
    """
    global _gate
    if _gate is None:
        _gate = ApprovalGate()
    return _gate


def reset_approval_gate() -> None:
    """
    Resets the ApprovalGate singleton. Useful for testing.
    """
    global _gate
    _gate = None
