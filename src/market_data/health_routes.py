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

    @app.post("/market-data/admin/subscribe")
    async def market_data_admin_subscribe(body: dict) -> Any:
        """
        Admin helper to request a best-effort subscription for a token.
        Body: {"token": "<token_id>"}
        """
        token = body.get("token")
        if not token:
            return {"ok": False, "error": "token required"}
        try:
            # import lazily to avoid circular import at module load
            from webhook_server_fastapi import _market_data_adapter  # type: ignore
            if _market_data_adapter and getattr(_market_data_adapter, "subscribe", None):
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    loop.create_task(_market_data_adapter.subscribe(token))
                except RuntimeError:
                    import threading
                    threading.Thread(target=lambda: __import__("asyncio").run(_market_data_adapter.subscribe(token))).start()
                return {"ok": True, "scheduled": True, "token": token}
            else:
                return {"ok": False, "scheduled": False, "reason": "adapter_unavailable"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/market-data/subscriptions")
    async def market_data_subscriptions() -> Any:
        """
        Return current subscriptions with refcount (best-effort) and missing_cycles from reconcile state.
        """
        try:
            # lazy import to avoid circular module init issues
            import webhook_server_fastapi as ws  # type: ignore
            adapter = getattr(ws, "_market_data_adapter", None)
            desired_refcount = getattr(ws, "_market_data_desired_refcount", {}) or {}
            reconcile_state = getattr(ws, "_market_data_reconcile_state", None)
            if adapter is None:
                return {"ok": False, "error": "adapter_unavailable", "active_subscriptions": 0, "tokens": []}

            subs = set(getattr(adapter, "_subs", set()) or set())
            tokens = []
            # union of known tokens (adapter subs + last desired)
            all_tokens = sorted(set(list(subs) + list(desired_refcount.keys())))
            for tk in all_tokens:
                refcount = int(desired_refcount.get(tk, 1 if tk in subs else 0))
                missing = 0
                if reconcile_state is not None:
                    missing = int(getattr(reconcile_state, "missing_count", {}).get(tk, 0))
                tokens.append({"token_id": tk, "refcount": refcount, "missing_cycles": missing})

            return {"ok": True, "active_subscriptions": len(subs), "tokens": tokens}
        except Exception as e:
            return {"ok": False, "error": str(e)}

