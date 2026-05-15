import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple

import structlog

logger = structlog.get_logger()

# Type alias for event callbacks
EventCallback = Callable[[str, Any], Awaitable[None]]


class EventBus:
    """
    An asynchronous pub/sub event bus for internal Aura communication.
    Uses asyncio.Queue for thread-safe (within the loop) event dispatching.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[EventCallback]] = {}
        self._queue: Optional[asyncio.Queue[Tuple[str, Any]]] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_queue(self) -> asyncio.Queue[Tuple[str, Any]]:
        """Lazy initialization of the queue."""
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    async def _get_lock(self) -> asyncio.Lock:
        """Lazy initialization of the lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def subscribe(self, event_type: str, callback: EventCallback) -> None:
        """
        Registers a callback for a specific event type.
        Use '*' as event_type to subscribe to all events.
        """
        lock = await self._get_lock()
        async with lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = set()
            self._subscribers[event_type].add(callback)
            logger.debug(
                "event_subscribed",
                event_type=event_type,
                callback=getattr(callback, "__name__", str(callback)),
            )

    async def unsubscribe(self, event_type: str, callback: EventCallback) -> None:
        """
        Unregisters a callback from an event type.
        """
        lock = await self._get_lock()
        async with lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].discard(callback)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
                logger.debug(
                    "event_unsubscribed",
                    event_type=event_type,
                    callback=getattr(callback, "__name__", str(callback)),
                )

    async def publish(self, event_type: str, payload: Any) -> None:
        """
        Publishes an event to the bus. This method is async and safe to call
        from multiple concurrent tasks within the same event loop.
        """
        queue = self._get_queue()
        await queue.put((event_type, payload))
        logger.debug("event_published", event_type=event_type)

    def publish_threadsafe(self, event_type: str, payload: Any) -> None:
        """
        Publishes an event to the bus from a different thread.
        Useful for bridge logic or blocking OS calls.
        """
        queue = self._get_queue()
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(queue.put_nowait, (event_type, payload))
        logger.debug("event_published_threadsafe", event_type=event_type)

    async def dispatch_loop(self) -> None:
        """
        The main background loop that routes events from the queue to subscribers.
        This task should be started during application startup.
        """
        logger.info("event_bus_dispatch_loop_started")
        queue = self._get_queue()
        lock = await self._get_lock()

        try:
            while True:
                event_type, payload = await queue.get()

                # Get a copy of the subscribers under lock to avoid race conditions
                async with lock:
                    subscribers = list(self._subscribers.get(event_type, set()))
                    # Support wildcard subscribers
                    wildcards = list(self._subscribers.get("*", set()))
                    targets = list(set(subscribers + wildcards))

                if targets:
                    # Dispatch to all subscribers concurrently using gather
                    tasks = [
                        self._safe_dispatch(callback, event_type, payload)
                        for callback in targets
                    ]
                    await asyncio.gather(*tasks)

                queue.task_done()
        except asyncio.CancelledError:
            logger.info("event_bus_dispatch_loop_stopped")
            raise
        except Exception as e:
            logger.error("event_bus_fatal_error", error=str(e))

    async def _safe_dispatch(
        self, callback: EventCallback, event_type: str, payload: Any
    ) -> None:
        """
        Safely executes a single callback and logs any exceptions.
        """
        try:
            await callback(event_type, payload)
        except Exception as e:
            logger.error(
                "event_callback_failed",
                event_type=event_type,
                callback=getattr(callback, "__name__", str(callback)),
                error=str(e),
            )


# Singleton instance
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Returns the global EventBus singleton.
    """
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """
    Resets the EventBus singleton. Useful for testing.
    """
    global _bus
    _bus = None
