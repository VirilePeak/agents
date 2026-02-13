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

        # Try to introspect adapter state if available (safe import)
        adapter_present = False
        ws_connected = False
        active_subs = 0
        stale_tokens = 0
        notes = []
        try:
            # import lazily to avoid circular imports
            import src.market_data.adapter as _adapter_mod  # type: ignore
            # try to access global singleton if app set it
            try:
                from webhook_server_fastapi import _market_data_adapter  # type: ignore
                ada = _market_data_adapter
            except Exception:
                ada = None

            if ada is not None:
                adapter_present = True
                try:
                    ws_connected = bool(metrics.get("gauges", {}).get("market_data_ws_connected", 0))
                except Exception:
                    ws_connected = False
                try:
                    active_subs = len(getattr(ada, "_subs", []))
                except Exception:
                    active_subs = 0
                try:
                    # if cache provides stale detection, use it
                    cache = getattr(ada, "cache", None)
                    if cache and hasattr(cache, "count_stale_tokens"):
                        stale_tokens = cache.count_stale_tokens()
                    else:
                        stale_tokens = 0
                except Exception:
                    stale_tokens = 0
            else:
                notes.append("adapter_not_initialized")
        except Exception:
            # If introspection fails, keep telemetry-derived defaults
            notes.append("adapter_introspection_failed")

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

