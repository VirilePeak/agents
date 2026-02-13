from __future__ import annotations
from fastapi import FastAPI
from typing import Any
from src.market_data.telemetry import telemetry


def register(app: FastAPI) -> None:
    @app.get("/market-data/metrics")
    async def market_data_metrics() -> Any:
        return telemetry.get_snapshot()

    @app.get("/market-data/health")
    async def market_data_health() -> Any:
        metrics = telemetry.get_snapshot()
        last_msg_age = metrics.get("last_msg_age_s")
        eventbus_dropped = metrics.get("counters", {}).get("market_data_eventbus_dropped_total", 0)

        # Determine adapter presence primarily from telemetry gauge to avoid
        # brittle cross-module introspection in some runtime setups.
        notes = []
        gauges = metrics.get("gauges", {})
        ws_connected = bool(gauges.get("market_data_ws_connected", 0))
        adapter_present = ws_connected
        active_subs = 0
        stale_tokens = 0
        if not adapter_present:
            notes.append("adapter_not_initialized")

        ok = adapter_present and ws_connected
        return {
            "ok": ok,
            "ws_connected": ws_connected,
            "last_msg_age_s": last_msg_age,
            "active_subscriptions": active_subs,
            "stale_tokens": stale_tokens,
            "eventbus_dropped_total": eventbus_dropped,
            "notes": notes,
        }

