"""Repeated MTTR measurement for the node-failure scenarios.

Failure detection and recovery times vary run to run, so each scenario is
executed N times (default 3) and the report uses the median, with min-max kept
for spread. Individual runs are saved under results/runs/; the aggregated
median values are written to results/<mode>_<name>.json (the files the report
and the Office deliverables read), annotated with runs/min/max.

Run:  uv run python scripts/measure_mttr.py [N]
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tigergraph_ha import cluster, scenario  # noqa: E402

SCENARIOS = [
    ("kill_tg2", "kill", "tg2", None),
    ("stop_tg2", "stop", "tg2", None),
    ("pause_tg3", "pause", "tg3", None),
    ("partition_tg3", "partition", "tg3", None),
    ("component_gpe", "component", "tg2", "GPE_2"),
    ("kill_tg1", "kill", "tg1", None),
]


def wait_healthy(timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cluster.http_ok(cluster.gateway_url(), timeout=4) and cluster.person_count() is not None:
            return True
        time.sleep(4)
    return False


def med(values):
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 2) if vals else None


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    mode = cluster.ha_mode().lower()
    os.makedirs(os.path.join(scenario.RESULTS_DIR, "runs"), exist_ok=True)
    summary = {}

    for name, action, target, service in SCENARIOS:
        runs = []
        for i in range(1, n + 1):
            if not wait_healthy():
                print(f"!! cluster unhealthy before {name} run {i}; aborting scenario")
                break
            res = scenario.read_scenario(f"runs/{mode}_{name}_r{i}", action, target, service=service)
            runs.append(res)
            print(f"{name} run {i}/{n}: MTTR={res['mttr_s']} downtime={res['downtime_s']} "
                  f"avail={res['availability_pct']}% recovered={res['recovered']}")
        if not runs:
            continue

        mttrs = [r["mttr_s"] for r in runs]
        agg = dict(runs[-1])
        agg.update(
            scenario=f"{mode}_{name}", runs=len(runs),
            mttd_s=med([r["mttd_s"] for r in runs]),
            downtime_s=med([r["downtime_s"] for r in runs]),
            mttr_s=med(mttrs),
            mttr_min_s=min((v for v in mttrs if v is not None), default=None),
            mttr_max_s=max((v for v in mttrs if v is not None), default=None),
            availability_pct=med([r["availability_pct"] for r in runs]),
            recovered=all(r["recovered"] for r in runs),
        )
        with open(os.path.join(scenario.RESULTS_DIR, f"{mode}_{name}.json"), "w") as f:
            json.dump(agg, f, indent=2)
        summary[name] = {k: agg[k] for k in
                         ("runs", "mttd_s", "downtime_s", "mttr_s", "mttr_min_s", "mttr_max_s",
                          "availability_pct", "recovered")}
        print(f"== {name}: median MTTR={agg['mttr_s']}s (min {agg['mttr_min_s']} / max {agg['mttr_max_s']}), "
              f"median avail={agg['availability_pct']}%")

    with open(os.path.join(scenario.RESULTS_DIR, "mttr_summary.json"), "w") as f:
        json.dump({"mode": mode.upper(), "runs_per_scenario": n, "scenarios": summary}, f, indent=2)
    print("\nwrote results/mttr_summary.json")


if __name__ == "__main__":
    main()
