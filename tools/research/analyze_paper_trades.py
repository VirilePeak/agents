#!/usr/bin/env python3
"""
Analyze paper trades and print a Markdown summary.

Usage:
  python tools/research/analyze_paper_trades.py
"""
from __future__ import annotations
import json
import glob
from statistics import mean, median
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import math


def load_closed_trades(paths: List[str]) -> List[Dict[str, Any]]:
    trades = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if "realized_pnl" in obj:
                        trades.append(obj)
        except Exception:
            continue
    return trades


def summary_stats(trades: List[Dict[str, Any]]):
    pnls = [float(t.get("realized_pnl") or 0.0) for t in trades]
    total = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    breakeven = sum(1 for p in pnls if p == 0)
    winrate = (wins / total * 100.0) if total else 0.0
    avg = mean(pnls) if pnls else 0.0
    med = median(pnls) if pnls else 0.0
    avg_win = mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0.0
    avg_loss = mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0.0
    profit = sum(p for p in pnls if p > 0)
    loss = -sum(p for p in pnls if p < 0)
    profit_factor = (profit / loss) if loss > 0 else float("inf")
    expectancy = avg
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "winrate_pct": winrate,
        "avg_pnl": avg,
        "median_pnl": med,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
    }


def bucket_by(trades: List[Dict[str, Any]], key_func, min_size: int = 1):
    buckets = {}
    for t in trades:
        k = key_func(t)
        buckets.setdefault(k, []).append(t)
    # compute stats per bucket
    out = {}
    for k, items in buckets.items():
        if len(items) < min_size:
            continue
        out[k] = summary_stats(items)
    return out


def price_bucket(price: float) -> str:
    # buckets 0-0.1, 0.1-0.2, ... 0.9-1.0
    if price is None:
        return "na"
    try:
        p = float(price)
    except Exception:
        return "na"
    idx = min(9, max(0, int(p * 10)))
    lo = idx / 10.0
    hi = (idx + 1) / 10.0
    return f"{lo:.1f}-{hi:.1f}"


def print_markdown_report(trades: List[Dict[str, Any]]):
    s = summary_stats(trades)
    print("# Paper Trades Analysis\n")
    print("## Summary")
    print(f"- Total closed trades: **{s['total']}**")
    print(f"- Wins: {s['wins']}, Losses: {s['losses']}, Breakeven: {s['breakeven']}")
    print(f"- Winrate: **{s['winrate_pct']:.2f}%**")
    print(f"- Avg PnL: {s['avg_pnl']:.6f}, Median PnL: {s['median_pnl']:.6f}")
    print(f"- Avg Win: {s['avg_win']:.6f}, Avg Loss: {s['avg_loss']:.6f}")
    print(f"- Profit factor: {s['profit_factor']:.3f}")
    print(f"- Expectancy per trade: {s['expectancy']:.6f}\n")

    # avg entry price overall and by side
    entry_prices = [float(t.get("entry_price")) for t in trades if t.get("entry_price") is not None]
    avg_entry = mean(entry_prices) if entry_prices else None
    print("## Entry Price")
    print(f"- Avg entry price (all): {avg_entry}\n")
    by_side = {}
    for t in trades:
        side = t.get("side") or "unknown"
        if t.get("entry_price") is not None:
            by_side.setdefault(side, []).append(float(t.get("entry_price")))
    for side, prices in by_side.items():
        print(f"- Avg entry price ({side}): {mean(prices):.6f}")
    print("\n")

    # Buckets: by confidence
    print("## Buckets: by confidence")
    conf_buckets = bucket_by(trades, lambda t: int(t.get("confidence") or -1), min_size=1)
    print("|confidence|count|winrate%|expectancy|avg_pnl|")
    print("|---:|---:|---:|---:|---:|")
    for k in sorted(conf_buckets.keys()):
        v = conf_buckets[k]
        print(f"|{k}|{v['total']}|{v['winrate_pct']:.2f}|{v['expectancy']:.6f}|{v['avg_pnl']:.6f}|")
    print("\n")

    # By entry price buckets
    print("## Buckets: by entry price")
    price_buckets = bucket_by(trades, lambda t: price_bucket(t.get("entry_price")), min_size=1)
    print("|bucket|count|winrate%|expectancy|")
    print("|---|---:|---:|---:|")
    for k in sorted(price_buckets.keys()):
        v = price_buckets[k]
        print(f"|{k}|{v['total']}|{v['winrate_pct']:.2f}|{v['expectancy']:.6f}|")
    print("\n")

    # By session (best-effort from session_id)
    print("## Buckets: by session")
    sess_buckets = bucket_by(trades, lambda t: (t.get("session_id") or "unknown"), min_size=1)
    for k in sess_buckets:
        v = sess_buckets[k]
    print("|session|count|winrate%|expectancy|")
    print("|---|---:|---:|---:|")
    for k in sorted(sess_buckets.keys()):
        v = sess_buckets[k]
        print(f"|{k}|{v['total']}|{v['winrate_pct']:.2f}|{v['expectancy']:.6f}|")
    print("\n")

    # By spread_pct buckets if present
    def spread_bucket(t):
        sp = t.get("spread_pct") or t.get("spread") or None
        if sp is None:
            return "na"
        try:
            spf = float(sp)
        except Exception:
            return "na"
        # bucket pct into 0.0-0.01, 0.01-0.02 etc
        idx = min(9, int(spf * 100))
        return f"{idx/100:.2f}-{(idx+1)/100:.2f}"

    print("## Buckets: by spread_pct")
    sp_buckets = bucket_by(trades, lambda t: spread_bucket(t), min_size=1)
    print("|bucket|count|winrate%|expectancy|")
    print("|---|---:|---:|---:|")
    for k in sorted(sp_buckets.keys()):
        v = sp_buckets[k]
        print(f"|{k}|{v['total']}|{v['winrate_pct']:.2f}|{v['expectancy']:.6f}|")
    print("\n")

    # Top 5 worst segments (lowest expectancy) with sample size >=5
    segs = []
    # combine confidence and price buckets
    for k, v in conf_buckets.items():
        if v['total'] >= 5:
            segs.append(("conf:"+str(k), v['expectancy'], v['total']))
    for k, v in price_buckets.items():
        if v['total'] >= 5:
            segs.append(("price:"+str(k), v['expectancy'], v['total']))
    segs_sorted = sorted(segs, key=lambda x: x[1])
    print("## Worst segments (lowest expectancy, sample>=5)")
    for seg in segs_sorted[:5]:
        print(f"- {seg[0]}: expectancy={seg[1]:.6f} (n={seg[2]})")


def main():
    settings_files = []
    # primary
    p = Path("paper_trades.jsonl")
    if p.exists() and p.stat().st_size > 0:
        settings_files.append(str(p))
    else:
        settings_files.extend(sorted(glob.glob("paper_trades_legacy*.jsonl")))
    trades = load_closed_trades(settings_files)
    print_markdown_report(trades)


if __name__ == "__main__":
    main()

