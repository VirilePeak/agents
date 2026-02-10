import json
import os
import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class ConfirmationStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f)
        os.replace(tmp, self.path)

    def mark_pending(self, key: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self._data[key] = {"first_seen": time.time(), "payload": payload}
            try:
                self._save()
            except Exception:
                pass

    def pop_if_confirmed(self, key: str, delay: int, ttl: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Returns (confirmed, payload). If confirmed is True, pending entry is removed.
        """
        with self.lock:
            entry = self._data.get(key)
            if not entry:
                return False, None
            now = time.time()
            first = entry.get("first_seen", now)
            if now - first > ttl:
                # expired
                del self._data[key]
                try:
                    self._save()
                except Exception:
                    pass
                return False, None
            if now - first >= delay:
                payload = entry.get("payload")
                del self._data[key]
                try:
                    self._save()
                except Exception:
                    pass
                return True, payload
            return False, None

    def expire_all_older_than(self, ttl: int) -> int:
        removed = 0
        now = time.time()
        with self.lock:
            keys = list(self._data.keys())
            for k in keys:
                if now - self._data[k].get("first_seen", now) > ttl:
                    del self._data[k]
                    removed += 1
            if removed:
                try:
                    self._save()
                except Exception:
                    pass
        return removed


def check_market_quality_for_entry(best_bid: Optional[float], best_ask: Optional[float], ask_size: Optional[float], settings) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Return (ok, reason, details)
    """
    details = {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "ask_size": ask_size,
    }
    if best_ask is None:
        return False, "no_entry_price", details
    if best_bid is None:
        return False, "no_best_bid", details
    spread = best_ask - best_bid
    details["spread"] = spread
    if spread > settings.MAX_SPREAD_ENTRY:
        return False, "spread_too_wide", details
    if settings.ENFORCE_DEPTH:
        if ask_size is None:
            return False, "ask_size_unavailable", details
        try:
            if float(ask_size) < float(settings.MIN_ASK_SIZE):
                return False, "ask_size_too_small", details
        except Exception:
            return False, "ask_size_unavailable", details
    return True, "ok", details


def compute_time_to_market_end(market: Optional[Dict[str, Any]]) -> Tuple[Optional[int], str]:
    """
    Returns (seconds_to_end or None, reason)
    """
    if not market:
        return None, "end_time_unavailable"
    end_ts = market.get("end_time") or market.get("close_time") or market.get("end")
    if not end_ts:
        return None, "end_time_unavailable"
    try:
        # Expect ISO format; if numeric epoch, handle
        from datetime import datetime, timezone

        if isinstance(end_ts, (int, float)):
            end = datetime.fromtimestamp(float(end_ts), tz=timezone.utc)
        else:
            end = datetime.fromisoformat(str(end_ts).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        seconds = int((end - now).total_seconds())
        return seconds, "ok"
    except Exception:
        return None, "end_time_unavailable"

