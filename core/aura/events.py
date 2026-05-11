import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Set, Tuple

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
        self._queue: asyncio.Queue[Tuple[str, Any]] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, callback: EventCallback) -> None:
        """
        Registers a callback for a specific event type.
        Use '*' as event_type to subscribe to all events.
        """
        async with self._lock:
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
        async with self._lock:
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
        await self._queue.put((event_type, payload))
        logger.debug("event_published", event_type=event_type)

    def publish_threadsafe(self, event_type: str, payload: Any) -> None:
        """
        Publishes an event to the bus from a different thread.
        Useful for bridge logic or blocking OS calls.
        """
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self._queue.put_nowait, (event_type, payload))
        logger.debug("event_published_threadsafe", event_type=event_type)

    async def dispatch_loop(self) -> None:
        """
        The main background loop that routes events from the queue to subscribers.
        This task should be started during application startup.
        """
        logger.info("event_bus_dispatch_loop_started")
        try:
            while True:
                event_type, payload = await self._queue.get()

                # Get a copy of the subscribers under lock to avoid race conditions
                async with self._lock:
                    subscribers = list(self._subscribers.get(event_type, set()))
                    # Support wildcard subscribers
                    wildcards = list(self._subscribers.get("*", set()))
                    targets = list(set(subscribers + wildcards))

                if targets:
                    # Dispatch to all subscribers concurrently using gather
                    # We wrap each callback in a try-except via a helper to ensure
                    # one failing subscriber doesn't crash the loop.
                    tasks = [
                        self._safe_dispatch(callback, event_type, payload)
                        for callback in targets
                    ]
                    await asyncio.gather(*tasks)

                self._queue.task_done()
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
_bus = EventBus()


def get_event_bus() -> EventBus:
    """
    Returns the global EventBus singleton.
    """
    return _bus
