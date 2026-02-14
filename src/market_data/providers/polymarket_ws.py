from __future__ import annotations
import asyncio
import json
import logging
from typing import List, Optional

import websockets
import time

from ..schema import MarketEvent, OrderBookSnapshot
from .base import AbstractMarketDataProvider
from ..telemetry import telemetry

logger = logging.getLogger(__name__)


class PolymarketWSProvider(AbstractMarketDataProvider):
    def __init__(self, url: str, channel: str = "market", ping_interval: int = 10, pong_timeout: int = 30) -> None:
        super().__init__()
        self.url = url.rstrip("/") + f"/ws/{channel}"
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._subs: set[str] = set()
        self._ws = None
        self._ping_interval = ping_interval
        self._pong_timeout = pong_timeout

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        # close websocket if open
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def subscribe(self, token_ids: List[str]) -> None:
        for t in token_ids:
            self._subs.add(t)
        # If websocket connected, send subscription (safe check to avoid AttributeError)
        try:
            ws = self._ws
            connected = False
            if ws is not None:
                # Prefer explicit closed flag (works for multiple libs); fall back to library-specific attrs
                if hasattr(ws, "closed"):
                    connected = not bool(getattr(ws, "closed"))
                elif hasattr(ws, "state"):
                    try:
                        connected = getattr(ws, "state").name == "OPEN"
                    except Exception:
                        connected = False
                elif hasattr(ws, "open"):
                    connected = bool(getattr(ws, "open"))
            if connected:
                # send operation-based subscribe when already connected
                await self._send_subscribe_op(list(token_ids))
            else:
                logger.debug("subscribe: websocket not connected, queued tokens (no send)")
        except Exception:
            # Never raise out of subscribe - queue tokens for later when WS connects
            logger.exception("subscribe: unexpected error while attempting to send subscribe")

    async def unsubscribe(self, token_ids: List[str]) -> None:
        for t in token_ids:
            self._subs.discard(t)
        try:
            ws = self._ws
            connected = False
            if ws is not None:
                if hasattr(ws, "closed"):
                    connected = not bool(getattr(ws, "closed"))
                elif hasattr(ws, "state"):
                    try:
                        connected = getattr(ws, "state").name == "OPEN"
                    except Exception:
                        connected = False
                elif hasattr(ws, "open"):
                    connected = bool(getattr(ws, "open"))
            if connected:
                await self._send_unsubscribe(list(token_ids))
            else:
                logger.debug("unsubscribe: websocket not connected, removal queued")
        except Exception:
            logger.exception("unsubscribe: unexpected error while attempting to send unsubscribe")

    async def _send_subscribe(self, token_ids: List[str]) -> None:
        # legacy handshake (used on initial connect)
        if not token_ids:
            return
        msg = {"assets_ids": token_ids, "type": "market"}
        try:
            logger.debug("WS send handshake: count=%d sample=%s", len(token_ids), ",".join(str(x) for x in list(token_ids)[:3]))
            await self._ws.send(json.dumps(msg))
        except Exception as e:
            logger.debug("handshake send failed: %s", e)

    async def _send_subscribe_op(self, token_ids: List[str]) -> None:
        # operation-based subscribe (used after connect)
        if not token_ids:
            return
        msg = {"assets_ids": token_ids, "operation": "subscribe"}
        try:
            logger.debug("WS send subscribe_op: count=%d sample=%s", len(token_ids), ",".join(str(x) for x in list(token_ids)[:3]))
            await self._ws.send(json.dumps(msg))
            try:
                telemetry.incr("market_data_subscribe_sent_total", 1)
            except Exception:
                pass
        except Exception as e:
            logger.debug("subscribe_op send failed: %s", e)

    async def _send_unsubscribe(self, token_ids: List[str]) -> None:
        if not token_ids:
            return
        msg = {"assets_ids": token_ids, "operation": "unsubscribe"}
        try:
            logger.debug("WS send unsubscribe_op: count=%d sample=%s", len(token_ids), ",".join(str(x) for x in list(token_ids)[:3]))
            await self._ws.send(json.dumps(msg))
            try:
                telemetry.incr("market_data_unsubscribe_sent_total", 1)
            except Exception:
                pass
        except Exception as e:
            logger.debug("unsubscribe_op send failed: %s", e)

    async def _handle_dict_msg(self, m: dict) -> None:
        """
        Normalize and dispatch a single message dict (book / price_change / trade).
        Extracted into a method for clarity and testability.
        """
        try:
            etype = m.get("event_type") or m.get("type") or m.get("topic")
            token = m.get("asset_id") or m.get("assetId") or m.get("market") or m.get("asset")
            # update last-msg timestamp for telemetry (use wall clock)
            try:
                telemetry.set_last_msg_ts(time.time())
            except Exception:
                pass

            if etype == "book":
                bids = m.get("bids") or m.get("buys") or []
                asks = m.get("asks") or m.get("sells") or []
                raw_ob = {"bids": bids, "asks": asks}
                snapshot = OrderBookSnapshot.from_raw(str(m.get("asset_id") or token), raw_ob, source="ws")
                ev = MarketEvent(
                    ts=float(m.get("timestamp") or 0)/1000.0 if m.get("timestamp") else float(asyncio.get_event_loop().time()),
                    type="book",
                    token_id=snapshot.token_id,
                    best_bid=snapshot.best_bid,
                    best_ask=snapshot.best_ask,
                    spread_pct=snapshot.spread_pct,
                    data=m,
                )
                if self.on_event:
                    try:
                        self.on_event(ev)
                    except Exception:
                        logger.exception("on_event handler failed")
                try:
                    telemetry.incr("market_data_messages_total", 1)
                    telemetry.set_gauge("market_data_active_subscriptions", float(len(self._subs)))
                except Exception:
                    pass
            elif etype == "price_change":
                changes = m.get("price_changes") or m.get("priceChanges") or []
                for pc in changes:
                    token_id = str(pc.get("asset_id") or pc.get("assetId") or token)
                    ev = MarketEvent(
                        ts=float(m.get("timestamp") or 0)/1000.0 if m.get("timestamp") else float(asyncio.get_event_loop().time()),
                        type="price_change",
                        token_id=token_id,
                        best_bid=pc.get("best_bid"),
                        best_ask=pc.get("best_ask"),
                        spread_pct=None,
                        data=pc,
                    )
                    if self.on_event:
                        try:
                            self.on_event(ev)
                        except Exception:
                            logger.exception("on_event handler failed")
                    try:
                        telemetry.incr("market_data_messages_total", 1)
                        telemetry.set_gauge("market_data_active_subscriptions", float(len(self._subs)))
                    except Exception:
                        pass
            elif etype == "last_trade_price":
                token_id = str(m.get("asset_id") or token)
                ev = MarketEvent(
                    ts=float(m.get("timestamp") or 0)/1000.0 if m.get("timestamp") else float(asyncio.get_event_loop().time()),
                    type="trade",
                    token_id=token_id,
                    best_bid=None,
                    best_ask=None,
                    spread_pct=None,
                    data=m,
                )
                if self.on_event:
                    try:
                        self.on_event(ev)
                    except Exception:
                        logger.exception("on_event handler failed")
                try:
                    telemetry.incr("market_data_messages_total", 1)
                    telemetry.set_gauge("market_data_active_subscriptions", float(len(self._subs)))
                except Exception:
                    pass
            else:
                # ignore other types
                return
        except Exception:
            logger.exception("processing single ws message failed")

    async def _run_loop(self) -> None:
        backoff = 1.0
        while self._running:
            try:
                logger.info("Connecting to Polymarket WS %s", self.url)
                async with websockets.connect(self.url, ping_interval=self._ping_interval, ping_timeout=self._pong_timeout) as ws:
                    self._ws = ws
                    telemetry.set_gauge("market_data_ws_connected", 1.0)
                    backoff = 1.0
                    # initial handshake subscribe if any (type=market)
                    if self._subs:
                        await self._send_subscribe(list(self._subs))
                        # After handshake, attempt to flush pending subscribe operations as well
                        try:
                            await self._send_subscribe_op(list(self._subs))
                            try:
                                telemetry.incr("market_data_subscribe_sent_total", 1)
                            except Exception:
                                pass
                        except Exception:
                            logger.debug("failed to flush subscribe_op after handshake")

                    async for raw in ws:
                        # count raw messages immediately for diagnostics
                        try:
                            telemetry.incr("market_data_raw_messages_total", 1)
                        except Exception:
                            pass
                        # raw may be bytes or str
                        try:
                            if isinstance(raw, (bytes, bytearray)):
                                raw_s = raw.decode("utf-8", errors="ignore")
                            else:
                                raw_s = str(raw)
                        except Exception:
                            raw_s = str(raw)
                        try:
                            parsed = json.loads(raw_s)
                        except Exception:
                            try:
                                telemetry.incr("market_data_parse_errors_total", 1)
                            except Exception:
                                pass
                            continue

                        # helper to process dict messages moved into class method _handle_dict_msg

                        # msg may be a list (batch) or a single dict
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, dict):
                                    await self._handle_dict_msg(item)
                                else:
                                    try:
                                        telemetry.incr("market_data_parse_errors_total", 1)
                                    except Exception:
                                        pass
                            continue

                        if not isinstance(parsed, dict):
                            try:
                                telemetry.incr("market_data_parse_errors_total", 1)
                            except Exception:
                                pass
                            continue

                        await self._handle_dict_msg(parsed)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("WebSocket connection error: %s", e)
                telemetry.incr("market_data_reconnect_total", 1)
                telemetry.set_gauge("market_data_ws_connected", 0.0)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
        logger.info("PolymarketWSProvider stopped")

    @staticmethod
    def parse_raw_message(msg: dict):
        # Parse raw Polymarket WS message dict into list of MarketEvent instances.
        events = []
        etype = msg.get("event_type") or msg.get("type") or msg.get("topic")
        if etype == "book":
            token = str(msg.get("asset_id") or msg.get("assetId") or msg.get("market") or "")
            ev = MarketEvent(ts=float(msg.get("timestamp") or 0)/1000.0 if msg.get("timestamp") else time.time(), type="book", token_id=token, best_bid=None, best_ask=None, spread_pct=None, data=msg)
            events.append(ev)
        elif etype == "price_change":
            changes = msg.get("price_changes") or msg.get("priceChanges") or []
            for pc in changes:
                token_id = str(pc.get("asset_id") or pc.get("assetId") or "")
                ev = MarketEvent(ts=float(msg.get("timestamp") or 0)/1000.0 if msg.get("timestamp") else time.time(), type="price_change", token_id=token_id, best_bid=pc.get("best_bid"), best_ask=pc.get("best_ask"), spread_pct=None, data=pc)
                events.append(ev)
        elif etype == "last_trade_price":
            token_id = str(msg.get("asset_id") or "")
            ev = MarketEvent(ts=float(msg.get("timestamp") or 0)/1000.0 if msg.get("timestamp") else time.time(), type="trade", token_id=token_id, best_bid=None, best_ask=None, spread_pct=None, data=msg)
            events.append(ev)
        return events

