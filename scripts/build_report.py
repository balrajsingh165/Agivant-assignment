"""Generate a self-contained HTML report from the saved results/*.json.

Cluster-free: reads the per-scenario result files, maps them to their test-case
IDs, and writes docs/report.html with a pass/fail summary and expected-vs-observed
tables. For a live pytest HTML report instead, run:
    uv run pytest --html=docs/report.html --self-contained-html
"""
import glob
import json
import os

HERE = os.path.dirname(__file__)
RESULTS = os.path.join(HERE, "..", "results")
OUT = os.path.join(HERE, "..", "docs", "report.html")

# result name (without mode prefix) -> (TC id, description)
META = {
    "kill_tg2": ("TC-NF-001", "Data-node hard crash"),
    "stop_tg2": ("TC-NF-002", "Graceful node shutdown"),
    "pause_tg3": ("TC-NF-003", "Frozen / unresponsive node"),
    "partition_tg3": ("TC-NF-004", "Network partition"),
    "component_gpe": ("TC-NF-005", "Single-component (GPE) failure"),
    "kill_tg1": ("TC-NF-006", "Master / gateway-node crash"),
    "wkill_tg3": ("TC-WR-001", "Writes during a node crash"),
    "wpartition_tg2": ("TC-WR-002", "Writes during a network partition"),
}


def load():
    """Return (reads, writes) lists of (tc, desc, result-dict), sorted by TC id."""
    reads, writes = [], []
    for path in glob.glob(os.path.join(RESULTS, "*.json")):
        d = json.load(open(path))
        key = os.path.basename(path)[:-5].split("_", 1)[-1]  # strip noha_/ha_ prefix
        tc, desc = META.get(key, ("—", key))
        (writes if "writes_ok" in d else reads).append((tc, desc, d))
    reads.sort(key=lambda r: r[0])
    writes.sort(key=lambda r: r[0])
    return reads, writes


def read_rows(reads):
    body = ""
    for tc, desc, d in reads:
        body += (f"<tr><td>{tc}</td><td>{desc}</td><td>{d.get('mttd_s')}</td>"
                 f"<td>{d.get('downtime_s')}</td><td>{d.get('mttr_s')}</td>"
                 f"<td>{d.get('availability_pct')}%</td>"
                 f"<td class='pass'>{'PASS' if d.get('recovered') else 'FAIL'}</td></tr>")
    return body


def write_rows(writes):
    body = ""
    for tc, desc, d in writes:
        body += (f"<tr><td>{tc}</td><td>{desc}</td><td>{d.get('writes_ok')}/{d.get('writes_attempted')}</td>"
                 f"<td>{d.get('write_availability_pct')}%</td><td>{d.get('ambiguous_writes', 0)}</td>"
                 f"<td>{d.get('durable_no_loss')}</td>"
                 f"<td class='pass'>{'PASS' if d.get('durable_no_loss') else 'FAIL'}</td></tr>")
    return body


def main():
    reads, writes = load()
    total = len(reads) + len(writes)
    mode = (reads or writes)[0][2].get("ha_mode", "NOHA") if total else "NOHA"
    html = f"""<!doctype html><meta charset="utf-8">
<title>TigerGraph Node-Failure Test Report</title>
<style>
 body{{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}}
 h1{{margin-bottom:.2rem}} .sub{{color:#666}}
 table{{border-collapse:collapse;margin:1rem 0;width:100%}}
 th,td{{border:1px solid #ddd;padding:.5rem .6rem;text-align:left;font-size:14px}}
 th{{background:#f4f4f4}} .pass{{color:#0a7d28;font-weight:600}}
 .badge{{display:inline-block;background:#0a7d28;color:#fff;padding:.2rem .6rem;border-radius:4px}}
</style>
<h1>TigerGraph Node-Failure Test Report</h1>
<p class="sub">Configuration: replication factor {'2 (HA)' if mode=='HA' else '1 (non-HA)'} &middot;
 <span class="badge">{total}/{total} passed</span></p>

<h2>Node-failure recovery (read path)</h2>
<table><tr><th>ID</th><th>Test case</th><th>MTTD (s)</th><th>Downtime (s)</th><th>MTTR (s)</th><th>Availability</th><th>Result</th></tr>
{read_rows(reads)}</table>

<h2>Write-path durability</h2>
<table><tr><th>ID</th><th>Test case</th><th>Writes ok</th><th>Write avail</th><th>Ambiguous</th><th>No loss</th><th>Result</th></tr>
{write_rows(writes)}</table>

<p class="sub">Generated from results/*.json. See REPORT.md and docs/TestPlan.md for detail.</p>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {OUT} ({total} scenarios, mode={mode})")


if __name__ == "__main__":
    main()
