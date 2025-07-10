# core/event_bus.py
"""
Event bus for decoupled communication.
"""
from typing import Dict, List, Callable, Any
from collections import defaultdict
import asyncio


class EventBus:
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe handler to event type"""
        self.handlers[event_type].append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish event to all subscribers"""
        for handler in self.handlers[event_type]:
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                handler(data)


# Global event bus instance
event_bus = EventBus()
