from __future__ import annotations
import asyncio
import logging
from typing import Optional, Set, List

from .schema import OrderBookSnapshot, MarketEvent
from .event_bus import AsyncEventBus
from .cache import OrderBookCache
from .providers.polymarket_ws import PolymarketWSProvider

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MarketDataAdapter:
    def __init__(self, provider: Optional[object] = None) -> None:
        settings = get_settings()
        url = getattr(settings, "MARKET_DATA_WS_URL", "wss://ws-subscriptions-clob.polymarket.com")
        ping = getattr(settings, "MARKET_DATA_WS_PING_INTERVAL", 10)
        pong = getattr(settings, "MARKET_DATA_WS_PONG_TIMEOUT", 30)
        self.event_bus = AsyncEventBus(queue_maxsize=getattr(settings, "MARKET_DATA_BUS_QUEUE_SIZE", 1000))
        self.cache = OrderBookCache()
        self.provider = provider or PolymarketWSProvider(url, channel="market", ping_interval=ping, pong_timeout=pong)
        self.provider.on_event = self._on_provider_event
        self._subs: Set[str] = set()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await self.provider.start()
        logger.info("MarketDataAdapter started")

    async def stop(self) -> None:
        await self.provider.stop()
        self._started = False
        logger.info("MarketDataAdapter stopped")

    async def subscribe(self, token_id: str) -> None:
        if token_id in self._subs:
            return
        self._subs.add(token_id)
        await self.provider.subscribe([token_id])

    async def unsubscribe(self, token_id: str) -> None:
        if token_id not in self._subs:
            return
        self._subs.discard(token_id)
        await self.provider.unsubscribe([token_id])

    def get_orderbook(self, token_id: str) -> OrderBookSnapshot | None:
        snap = self.cache.get(token_id)
        return snap

    def _on_provider_event(self, ev: MarketEvent) -> None:
        # called in provider's event loop; schedule cache update + bus publish
        try:
            # Prefer scheduling on existing running loop (thread-safe)
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(asyncio.create_task, self._handle_event(ev))
            except RuntimeError:
                # No running loop in this thread - run synchronously (blocking) to support tests
                asyncio.run(self._handle_event(ev))
        except Exception:
            # fallback: schedule with ensure_future
            try:
                asyncio.ensure_future(self._handle_event(ev))
            except Exception:
                logger.exception("failed to schedule event handling")

    async def _handle_event(self, ev: MarketEvent) -> None:
        # update cache for book/price_change/trade if applicable
        try:
            if ev.type == "book":
                # build a lightweight snapshot from ev.data if present
                raw = ev.data or {}
                snapshot = OrderBookSnapshot.from_raw(ev.token_id, raw, source="ws")
                self.cache.update(snapshot)
            # publish event to bus
            await self.event_bus.publish(ev)
        except Exception:
            logger.exception("error handling provider event")

