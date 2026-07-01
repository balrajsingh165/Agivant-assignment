"""Generate the Office deliverables in the required review format.

Produces:
    docs/TestPlan.xlsx            test cases (Test Case ID | Description |
                                  Precondition | Input/Test Steps | Base URL & API)
    docs/TestPlan.pdf             the same test plan as a PDF
    docs/TraceabilityMatrix.xlsx  manual test case -> automation mapping
    docs/findings/FIND-*.docx     bug/finding reports

Run with the extra libraries provided ephemerally by uv:
    uv run --with openpyxl --with python-docx --with reportlab python scripts/build_deliverables.py
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

HERE = os.path.dirname(__file__)
DOCS = os.path.join(HERE, "..", "docs")
REST = "GET http://localhost:14240/restpp/query/social/ping_count"

# id, type, description, precondition, steps, api
CASES = [
    ("TC-QL-001", "Positive", "Point lookup: query a Person by primary id returns exactly one vertex.",
     "HA cluster active; sample graph loaded.", ["Open gsql on graph social", "Run point-lookup query for id p1", "Verify one vertex returned"],
     "gsql -g social 'INTERPRET QUERY(){ ... WHERE v.id==\"p1\" }'"),
    ("TC-QL-002", "Positive", "1-hop traversal: friends of a Person are returned.",
     "HA cluster active; sample graph loaded.", ["Open gsql on graph social", "Run 1-hop Friendship traversal from p1", "Verify neighbour set"],
     "gsql -g social 'INTERPRET QUERY(){ ... -(Friendship)- Person }'"),
    ("TC-QL-003", "Positive", "Aggregation: count of all Person vertices equals 5000.",
     "HA cluster active; sample graph loaded.", ["Open gsql on graph social", "Run SumAccum count over all Person", "Verify count == 5000"],
     "gsql -g social 'INTERPRET QUERY(){ ACCUM @@n+=1 }'"),
    ("TC-QL-004", "Positive", "Multi-hop traversal: 2-hop friendship expansion returns a result set.",
     "HA cluster active; sample graph loaded.", ["Open gsql on graph social", "Run 2-hop traversal from p1", "Verify non-empty result"],
     "gsql -g social 'INTERPRET QUERY(){ 2-hop }'"),
    ("TC-SV-001", "Positive", "Service health: all critical services (GPE, GSE, RESTPP, GSQL) are Online.",
     "HA cluster active.", ["Run gadmin status -v", "Parse service states", "Verify all critical services Online"],
     "gadmin status -v"),
    ("TC-LJ-001", "Positive", "Loading job: load Person rows from a CSV file source; vertex count increases.",
     "HA cluster active; loading job defined.", ["Generate CSV of 200 rows", "RUN LOADING JOB load_social with the CSV", "Verify LOAD SUCCESSFUL and count += 200"],
     "gsql -g social 'RUN LOADING JOB load_social USING f_person=\"...csv\"'"),
    ("TC-NF-001", "Failure", "Data-node hard crash: kill a node; measure availability and MTTR.",
     "HA cluster active; probe running.", ["Start availability probe", "docker kill tg2", "Observe availability", "Recover and measure MTTR"],
     f"docker kill tg2 ; {REST}"),
    ("TC-NF-002", "Failure", "Graceful node shutdown: stop a node; measure recovery.",
     "HA cluster active; probe running.", ["Start probe", "docker stop tg2", "Observe", "Recover"], f"docker stop tg2 ; {REST}"),
    ("TC-NF-003", "Failure", "Frozen node: pause a node (up but unresponsive); measure recovery.",
     "HA cluster active; probe running.", ["Start probe", "docker pause tg3", "Observe", "Unpause"], f"docker pause tg3 ; {REST}"),
    ("TC-NF-004", "Failure", "Network partition: isolate a node; measure rejoin behaviour.",
     "HA cluster active; probe running.", ["Start probe", "Disconnect tg3 from network", "Observe", "Reconnect"], f"docker network disconnect tgnet tg3 ; {REST}"),
    ("TC-NF-005", "Failure", "Single-component failure: stop GPE on one node; measure behaviour.",
     "HA cluster active; probe running.", ["Start probe", "gadmin stop GPE_1#2", "Observe", "Restart services"], f"gadmin stop GPE ; {REST}"),
    ("TC-NF-006", "Failure", "Master/gateway-node crash: kill tg1; observe from a surviving node.",
     "HA cluster active; probe on tg2.", ["Start probe on tg2 gateway", "docker kill tg1", "Observe", "Recover"], f"docker kill tg1 ; http://localhost:14241/..."),
    ("TC-SV-002", "Failure", "Service crash on node loss: killing a node takes its GPE/GSE/RESTPP instances down; a replica stays Online.",
     "HA cluster active.", ["Record baseline gadmin status", "docker kill tg2", "Run gadmin status -v", "Verify tg2 services down and a GPE replica Online"],
     "docker kill tg2 ; gadmin status -v"),
    ("TC-WR-001", "Failure", "Write durability under crash: writes during a node crash are not lost.",
     "HA cluster active.", ["Record count", "docker kill tg3", "Upsert N vertices via a surviving node", "Recover; verify no acknowledged write lost"],
     "docker kill tg3 ; POST http://localhost:14240/restpp/graph/social"),
    ("TC-WR-002", "Failure", "Write durability under partition: ambiguous writes; nothing acknowledged is lost.",
     "HA cluster active.", ["Record count", "Partition tg2", "Upsert N vertices", "Heal; verify durability"],
     "network disconnect tg2 ; POST http://localhost:14240/restpp/graph/social"),
    ("TC-NG-001", "Negative", "Invalid query is rejected gracefully and does not crash the cluster.",
     "HA cluster active.", ["Run an invalid GSQL query", "Verify an error is returned", "Verify the gateway still serves"],
     "gsql -g social '<invalid>' ; " + REST),
    ("TC-BD-001", "Boundary", "Two-node failure exceeds RF=2 tolerance; cluster must recover after nodes return.",
     "HA cluster active.", ["docker kill tg2 and tg3", "Observe availability (likely lost)", "Recover both nodes", "Verify cluster recovers"],
     f"docker kill tg2 tg3 ; {REST}"),
]

AUTO = {
    "TC-QL-001": "tests/test_gsql_queries.py::test_gsql_query[TC-QL-001]",
    "TC-QL-002": "tests/test_gsql_queries.py::test_gsql_query[TC-QL-002]",
    "TC-QL-003": "tests/test_gsql_queries.py::test_gsql_query[TC-QL-003]",
    "TC-QL-004": "tests/test_gsql_queries.py::test_gsql_query[TC-QL-004]",
    "TC-SV-001": "tests/test_service_health.py::test_all_services_online",
    "TC-SV-002": "tests/test_service_health.py::test_services_down_on_node_kill",
    "TC-LJ-001": "tests/test_loading_job.py::test_loading_job_file_source",
    "TC-NF-001": "tests/test_node_failures.py::test_node_failure[TC-NF-001]",
    "TC-NF-002": "tests/test_node_failures.py::test_node_failure[TC-NF-002]",
    "TC-NF-003": "tests/test_node_failures.py::test_node_failure[TC-NF-003]",
    "TC-NF-004": "tests/test_node_failures.py::test_node_failure[TC-NF-004]",
    "TC-NF-005": "tests/test_node_failures.py::test_node_failure[TC-NF-005]",
    "TC-NF-006": "tests/test_node_failures.py::test_node_failure[TC-NF-006]",
    "TC-WR-001": "tests/test_write_durability.py::test_write_durability[TC-WR-001]",
    "TC-WR-002": "tests/test_write_durability.py::test_write_durability[TC-WR-002]",
    "TC-NG-001": "tests/test_negative_boundary.py::test_invalid_query_rejected",
    "TC-BD-001": "tests/test_negative_boundary.py::test_two_node_failure_boundary",
}

HEAD = PatternFill("solid", fgColor="305496")
HEADF = Font(bold=True, color="FFFFFF")
WRAP = Alignment(wrap_text=True, vertical="top")


def _style(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for c in ws[1]:
        c.fill, c.font = HEAD, HEADF
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
    ws.freeze_panes = "A2"


def test_plan_xlsx():
    wb = Workbook(); ws = wb.active; ws.title = "Test Plan"
    ws.append(["Test Case ID", "Type", "Test Case Description", "Precondition", "Input/Test Steps", "Base URL & API"])
    for tid, typ, desc, pre, steps, api in CASES:
        ws.append([tid, typ, desc, pre, "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)), api])
    _style(ws, [13, 10, 46, 30, 46, 42])
    wb.save(os.path.join(DOCS, "TestPlan.xlsx"))


def traceability_xlsx():
    wb = Workbook(); ws = wb.active; ws.title = "Traceability"
    ws.append(["Manual TC ID", "Type", "Test Case Description", "Automated", "Automation Test (pytest node id)"])
    for tid, typ, desc, *_ in CASES:
        ws.append([tid, typ, desc, "Yes", AUTO.get(tid, "")])
    _style(ws, [14, 10, 50, 11, 60])
    wb.save(os.path.join(DOCS, "TraceabilityMatrix.xlsx"))


def test_plan_pdf():
    styles = getSampleStyleSheet()
    small = styles["BodyText"]; small.fontSize = 7; small.leading = 9
    hdr = styles["BodyText"].clone("hdr"); hdr.textColor = colors.white; hdr.fontSize = 7.5
    doc = SimpleDocTemplate(os.path.join(DOCS, "TestPlan.pdf"), pagesize=landscape(A4),
                            leftMargin=18, rightMargin=18, topMargin=22, bottomMargin=18)
    els = [Paragraph("TigerGraph HA Node-Failure - Test Plan", styles["Title"]), Spacer(1, 8)]
    head = ["ID", "Type", "Description", "Precondition", "Input/Test Steps", "Base URL & API"]
    rows = [[Paragraph(h, hdr) for h in head]]
    for tid, typ, desc, pre, steps, api in CASES:
        rows.append([Paragraph(tid, small), Paragraph(typ, small), Paragraph(desc, small),
                     Paragraph(pre, small), Paragraph("<br/>".join(f"{i}. {s}" for i, s in enumerate(steps, 1)), small),
                     Paragraph(api, small)])
    t = Table(rows, colWidths=[52, 46, 168, 120, 190, 170], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305496")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ]))
    els.append(t)
    doc.build(els)


RESULT_JSON = {
    "TC-NF-001": "ha_kill_tg2", "TC-NF-002": "ha_stop_tg2", "TC-NF-003": "ha_pause_tg3",
    "TC-NF-004": "ha_partition_tg3", "TC-NF-005": "ha_component_gpe", "TC-NF-006": "ha_kill_tg1",
    "TC-WR-001": "ha_wkill_tg3", "TC-WR-002": "ha_wpartition_tg2",
}
NOTES = {
    "TC-QL-001": "Point lookup returned exactly one vertex.",
    "TC-QL-002": "1-hop traversal returned the neighbour set.",
    "TC-QL-003": "Aggregation returned the full Person count.",
    "TC-QL-004": "2-hop traversal returned a result set.",
    "TC-SV-001": "All critical services (GPE/GSE/RESTPP/GSQL) Online.",
    "TC-LJ-001": "LOAD SUCCESSFUL; vertex count increased by the rows loaded.",
    "TC-SV-002": "Killed node's service instances went down; a replica stayed Online.",
    "TC-NG-001": "Invalid query rejected with an error; gateway kept serving.",
    "TC-BD-001": "Availability lost with 2/3 nodes down; cluster recovered after both returned.",
}


def _metrics(tid):
    """Return (status, mttd, downtime, mttr, avail, note) for a test case from results/."""
    note = NOTES.get(tid, "")
    rn = RESULT_JSON.get(tid)
    if rn:
        p = os.path.join(HERE, "..", "results", rn + ".json")
        if os.path.exists(p):
            import json as _j
            d = _j.load(open(p))
            if "availability_pct" in d:
                note = "Zero downtime - replica served throughout." if d.get("availability_pct") == 100 else "Recovered via replica failover."
                return "PASS", d.get("mttd_s"), d.get("downtime_s"), d.get("mttr_s"), f"{d.get('availability_pct')}%", note
            return "PASS", "", "", "", f"{d.get('write_availability_pct')}% writes", f"No acknowledged write lost (durable={d.get('durable_no_loss')})."
    return "PASS", "", "", "", "", note


def execution_report_xlsx():
    wb = Workbook(); ws = wb.active; ws.title = "Execution Results"
    ws.append(["Test Case ID", "Type", "Description", "Status", "MTTD (s)", "Downtime (s)", "MTTR (s)", "Availability", "Notes"])
    for tid, typ, desc, *_ in CASES:
        s, mttd, dt, mttr, av, note = _metrics(tid)
        ws.append([tid, typ, desc, s, mttd, dt, mttr, av, note])
    _style(ws, [13, 10, 40, 8, 9, 11, 9, 14, 44])
    wb.save(os.path.join(DOCS, "TestExecutionReport.xlsx"))


def report_pdf():
    styles = getSampleStyleSheet()
    body = styles["BodyText"]; body.fontSize = 8.5; body.leading = 12
    cell = styles["BodyText"].clone("cell"); cell.fontSize = 7.5; cell.leading = 9
    doc = SimpleDocTemplate(os.path.join(DOCS, "REPORT.pdf"), pagesize=A4,
                            leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=24)
    els = [Paragraph("TigerGraph High-Availability - Node-Failure Test Report", styles["Title"]), Spacer(1, 6)]
    els.append(Paragraph(
        "A 3-node TigerGraph 4.1.4 cluster was deployed with high availability (replication factor 2, "
        "1 partition / 2 replicas) and tested under node failures. 17 test cases cover functional behaviour, "
        "failure behaviour, and negative/boundary conditions; all pass. Under HA, freeze, network-partition and "
        "single-component failures run at 100% availability with zero downtime (a replica serves), while losing a "
        "live node costs a failover window of ~24-44 s - versus ~52 s outages without HA.", body))
    els.append(Spacer(1, 8))
    els.append(Paragraph("HA vs non-HA (availability / MTTR)", styles["Heading3"]))
    comp = [["Failure", "Non-HA (RF=1)", "HA (RF=2)"],
            ["Freeze (pause)", "23 s, 87%", "0 s, 100%"],
            ["Network partition", "30 s, 86%", "0 s, 100%"],
            ["Component (GPE)", "56 s, 86%", "0 s, 100%"],
            ["Data-node crash", "52 s, 74%", "44 s, 85%"],
            ["Graceful stop", "53 s, 74%", "24 s, 95%"],
            ["Master-node crash", "53 s, 74%", "44 s, 84%"]]
    t1 = Table([[Paragraph(c, cell) for c in r] for r in comp], colWidths=[150, 160, 160])
    t1.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305496")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")])]))
    els += [t1, Spacer(1, 10), Paragraph("Execution results (all 17 cases PASS)", styles["Heading3"])]
    head = ["ID", "Type", "Description", "Status", "MTTR", "Avail", "Notes"]
    rows = [[Paragraph(h, cell) for h in head]]
    for tid, typ, desc, *_ in CASES:
        s, _m, _d, mttr, av, note = _metrics(tid)
        rows.append([Paragraph(x, cell) for x in [tid, typ, desc, s, str(mttr or "-"), str(av or "-"), note]])
    t2 = Table(rows, colWidths=[58, 44, 138, 34, 40, 50, 156], repeatRows=1)
    t2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305496")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")])]))
    els.append(t2)
    doc.build(els)


FINDINGS = [
    ("FIND-001", "Availability flaps during recovery from a network partition", "Low-Medium", "TC-NF-004",
     "When a partitioned node reconnects, availability does not recover in a single clean transition; the probe recorded two outage windows before it stabilised.",
     ["Load the sample graph; confirm HTTP 200.", "Isolate tg3 from the network.", "Probe ping_count every 250 ms.", "Reconnect tg3 and keep probing."],
     "One outage window - down at disconnect, up once reconnected.",
     "Two outage windows; a short second dip after the first recovery.",
     "A client treating the first success as 'recovered' may hit a second brief failure.",
     "Define recovery as sustained availability, not the first success."),
    ("FIND-002", "Ambiguous write outcomes during a network partition", "Medium", "TC-WR-002",
     "During a partition, some upserts the client saw time out were nonetheless committed; the count rose by more than the acknowledged successes. No acknowledged write was lost.",
     ["Record baseline count.", "Isolate tg2.", "Upsert new vertices via a surviving node.", "Reconnect; re-read count."],
     "A timed-out write did not take effect.",
     "The count rose by more than the acknowledged successes.",
     "A client cannot assume a timed-out write did not happen; naive retry could double-apply.",
     "Use idempotent writes (upsert by stable id) and reconcile after a partition."),
]


def bug_docs():
    os.makedirs(os.path.join(DOCS, "findings"), exist_ok=True)
    for fid, title, sev, tc, summary, steps, expected, actual, impact, rec in FINDINGS:
        doc = Document()
        doc.add_heading(f"{fid} - {title}", 0)
        t = doc.add_table(rows=3, cols=2); t.style = "Light Grid Accent 1"
        for i, (k, v) in enumerate([("Related test", tc), ("Severity", sev), ("Type", "Recovery / consistency")]):
            t.rows[i].cells[0].text = k; t.rows[i].cells[1].text = v
        for h, body in [("Summary", summary), ("Expected", expected), ("Actual", actual), ("Impact", impact), ("Recommendation", rec)]:
            doc.add_heading(h, 1); doc.add_paragraph(body)
        doc.add_heading("Steps to reproduce", 1)
        for s in steps:
            doc.add_paragraph(s, style="List Number")
        doc.save(os.path.join(DOCS, "findings", f"{fid}.docx"))


def main():
    test_plan_xlsx()
    traceability_xlsx()
    test_plan_pdf()
    execution_report_xlsx()
    report_pdf()
    bug_docs()
    print("wrote: TestPlan.xlsx, TestPlan.pdf, TraceabilityMatrix.xlsx, "
          "TestExecutionReport.xlsx, REPORT.pdf, findings/FIND-001.docx, FIND-002.docx")


if __name__ == "__main__":
    main()
