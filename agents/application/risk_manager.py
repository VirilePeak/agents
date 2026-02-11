from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Tuple

from src.config.settings import get_settings
from agents.application.position_manager import TradeStatus


class ExitReason(str, Enum):
    SOFT_STOP = "soft_stop"
    TIME_STOP = "time_stop"


@dataclass
class ExitCheck:
    should_exit: bool
    reason: ExitReason | None = None


@dataclass
class ExposureCheck:
    allowed: bool
    reason: str
    current_exposure: float
    proposed_exposure: float
    max_exposure: float


class RiskManager:
    """Lightweight risk manager used by the webhook server."""

    def __init__(self, initial_equity: float, max_exposure_pct: float, base_risk_pct: float):
        self.initial_equity = float(initial_equity)
        self.current_equity = float(initial_equity)
        self.max_exposure_pct = float(max_exposure_pct)
        self.base_risk_pct = float(base_risk_pct)

    def update_equity(self, realized_pnl: float) -> None:
        self.current_equity += float(realized_pnl or 0.0)

    def calculate_position_size(self, confidence: int | None, base_size: float | None) -> float:
        settings = get_settings()
        base = float(base_size if base_size is not None else settings.PAPER_USDC)
        if confidence is None:
            return max(0.01, base)
        # Aggressive confidence scaling: higher confidence = bigger size
        # conf 5: 1.0x, conf 6: 1.5x, conf 7: 2.0x, conf 8: 2.5x, conf 9+: 3.0x
        scale_map = {5: 1.0, 6: 1.5, 7: 2.0, 8: 2.5, 9: 3.0, 10: 3.0}
        scale = scale_map.get(confidence, 1.0 + max(0, confidence - settings.MIN_CONFIDENCE) * 0.5)
        return max(0.01, base * scale)

    def check_exposure(self, proposed_trade_size: float, active_trades: Dict[str, Any]) -> ExposureCheck:
        max_exposure = self.current_equity * self.max_exposure_pct
        current_exposure = 0.0
        for trade in active_trades.values():
            if getattr(trade, "status", None) in (
                TradeStatus.PENDING,
                TradeStatus.CONFIRMED,
                TradeStatus.ADDED,
                TradeStatus.HEDGED,
            ):
                current_exposure += float(getattr(trade, "total_size", 0.0) or 0.0)
        proposed_exposure = current_exposure + float(proposed_trade_size or 0.0)
        allowed = proposed_exposure <= max_exposure
        reason = "ok" if allowed else "max_exposure"
        return ExposureCheck(
            allowed=allowed,
            reason=reason,
            current_exposure=current_exposure,
            proposed_exposure=proposed_exposure,
            max_exposure=max_exposure,
        )

    def check_direction_limit(self, side: str, active_trades: Dict[str, Any]) -> Tuple[bool, str]:
        side = str(side).upper()
        for trade in active_trades.values():
            if getattr(trade, "status", None) in (
                TradeStatus.PENDING,
                TradeStatus.CONFIRMED,
                TradeStatus.ADDED,
                TradeStatus.HEDGED,
            ):
                if str(getattr(trade, "side", "")).upper() == side:
                    return False, f"existing_{side}_position"
        return True, "ok"

    def check_soft_stop(self, trade: Any, current_price: float) -> ExitCheck:
        settings = get_settings()
        entry_price = float(getattr(trade, "entry_price", 0.0) or 0.0)
        if entry_price <= 0 or current_price is None:
            return ExitCheck(False, None)
        threshold = float(settings.SOFT_STOP_ADVERSE_MOVE)
        side = str(getattr(trade, "side", "")).upper()
        # UP/BULL loses when price drops; DOWN/BEAR loses when price rises
        # Use absolute price move (not percentage of entry) for fairer stops
        # on binary markets where prices are bounded [0, 1]
        adverse_move = 0.0
        if side in ("UP", "BULL", "BUY_UP"):
            adverse_move = entry_price - current_price  # positive when price drops
        elif side in ("DOWN", "BEAR", "BUY_DOWN"):
            adverse_move = current_price - entry_price  # positive when price rises
        if adverse_move >= threshold:
            return ExitCheck(True, ExitReason.SOFT_STOP)
        return ExitCheck(False, None)

    def check_time_stop(self, trade: Any, current_price: float, bars_elapsed: int) -> ExitCheck:
        settings = get_settings()
        if bars_elapsed is None:
            return ExitCheck(False, None)
        if bars_elapsed >= int(settings.TIME_STOP_BARS):
            return ExitCheck(True, ExitReason.TIME_STOP)
        return ExitCheck(False, None)
