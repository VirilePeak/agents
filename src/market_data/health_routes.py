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
        return {
            "ok": False,
            "ws_connected": False,
            "last_msg_age_s": last_msg_age,
            "active_subscriptions": 0,
            "stale_tokens": 0,
            "eventbus_dropped_total": eventbus_dropped,
            "notes": ["adapter_not_initialized"],
        }

