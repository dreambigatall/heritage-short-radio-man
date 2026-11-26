"""Summarise runs.jsonl per stage and model: calls, failures, latency, units, GPU minutes, list price.

    python run.py costs          prints a Markdown table (paste it into COSTS.md)
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

from common import PRICING, RUNS_LOG


def summarise() -> str:
    rows = defaultdict(lambda: {"calls": 0, "ok": 0, "err": 0, "lat": [], "units": 0.0, "unit": "", "usd": 0.0})
    prices = json.loads(PRICING.read_text(encoding="utf-8")).get("models", {}) if PRICING.exists() else {}
    for line in RUNS_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r.get("stage"), r.get("model"))
        row = rows[k]
        row["calls"] += 1
        if r.get("status") == "ok":
            row["ok"] += 1
            if r.get("latency_s") is not None:
                row["lat"].append(r["latency_s"])
            if isinstance(r.get("units"), (int, float)):
                row["units"] += r["units"]
                row["unit"] = r.get("unit") or row["unit"]
            p = (prices.get(r.get("model")) or {}).get("usd_per_unit")
            if p is not None and isinstance(r.get("units"), (int, float)):
                row["usd"] += p * r["units"]
        else:
            row["err"] += 1
    out = ["| Stage | Model | Calls | OK | Failed | Median latency (s) | Total latency (s) | Units | List-price USD |",
           "|---|---|---|---|---|---|---|---|---|"]
    for (stage, model), r in sorted(rows.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        med = f"{statistics.median(r['lat']):.1f}" if r["lat"] else "–"
        tot = f"{sum(r['lat']):.0f}" if r["lat"] else "–"
        units = f"{r['units']:.0f} {r['unit']}" if r["units"] else "–"
        out.append(f"| {stage} | {model} | {r['calls']} | {r['ok']} | {r['err']} | {med} | {tot} | {units} | "
                   f"{r['usd']:.4f} |")
    return "\n".join(out)


def run() -> None:
    print(summarise())


if __name__ == "__main__":
    run()
