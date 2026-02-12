from typing import Optional, Dict, Any
import time
from src.config.settings import get_settings
from src.market_data.telemetry import telemetry


def place_entry_order_with_gate(
    polymarket,
    token_id: str,
    price: float,
    size: float,
    side: str = "BUY",
    confidence: Optional[int] = None,
    market_quality_healthy: Optional[bool] = None,
    adapter: Optional[object] = None,
    risk_manager: Optional[object] = None,
) -> Dict[str, Any]:
    """
    Central chokepoint for placing entry orders.
    Returns dict:
      - allowed: bool
      - reason: str
      - details: dict
      - order_id: str (if allowed)
    """
    details = {"token_id": token_id, "price": price, "size": size, "side": side, "ts": time.time()}
    # Use provided risk_manager if given; else try to obtain from running app or fallback to local instance
    rm = risk_manager
    if rm is None:
        try:
            from webhook_server_fastapi import get_risk_manager
            rm = get_risk_manager()
        except Exception:
            try:
                from agents.application.risk_manager import RiskManager
                settings = get_settings()
                rm = RiskManager(settings.INITIAL_EQUITY, settings.MAX_EXPOSURE_PCT, settings.BASE_RISK_PCT)
            except Exception:
                rm = None

    if rm:
        allowed, reason, gate_details = rm.check_entry_allowed(
            token_id=token_id,
            confidence=confidence,
            market_quality_healthy=market_quality_healthy,
            adapter=adapter or polymarket,
            now_ts=time.time(),
            proposed_size=size,
        )
        details.update(gate_details or {})
        if not allowed:
            # telemetry increments are done in RiskManager; ensure a log-friendly return
            return {"allowed": False, "reason": reason, "details": details}

    # Allowed: perform the order via polymarket, ensuring gate_checked flag
    try:
        order_id = polymarket.execute_order(price=price, size=size, side=side, token_id=token_id, gate_checked=True)
        return {"allowed": True, "reason": "ok", "details": details, "order_id": order_id}
    except Exception as e:
        telemetry.incr("market_data_execute_order_error_total", 1)
        return {"allowed": False, "reason": "execute_error", "details": {**details, "error": str(e)}}

