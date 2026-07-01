"""Shared fixtures: cluster readiness, HA mode, and expected-vs-observed recording."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tigergraph_ha import cluster  # noqa: E402


@pytest.fixture(scope="session")
def ha_mode():
    """'HA' when the license enables high availability, else 'NOHA'."""
    return cluster.ha_mode()


@pytest.fixture(scope="session", autouse=True)
def cluster_ready():
    """Skip the whole suite unless the cluster is up with the sample graph loaded."""
    if not cluster.http_ok(cluster.gateway_url(cluster.MASTER), timeout=10):
        pytest.skip("cluster gateway not reachable; run docker compose up + scripts/01-install.sh")
    if cluster.person_count() is None:
        pytest.skip("sample graph not loaded; run scripts/load-sample-graph.sh")


@pytest.fixture(autouse=True)
def healthy_cluster():
    """Wait for the cluster to be serving before each test, so tests are order-independent
    (a prior destructive test may still be recovering)."""
    for _ in range(50):
        if cluster.http_ok(cluster.gateway_url(), timeout=4) and cluster.person_count() is not None:
            return
        time.sleep(3)
    pytest.skip("cluster did not become healthy before the test started")


@pytest.fixture
def record_expectation(request):
    """Record expected-vs-observed rows, surfaced per test in the HTML report."""
    rows = []
    request.node._expectations = rows
    return lambda check, expected, observed: rows.append((check, str(expected), str(observed)))


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach recorded expectations to the HTML report and write a per-test log file."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    rows = getattr(item, "_expectations", None) or []
    if rows:
        try:
            from pytest_html import extras
            html = "<table border='1' cellpadding='4'><tr><th>Check</th><th>Expected</th><th>Observed</th></tr>"
            html += "".join(f"<tr><td>{c}</td><td>{e}</td><td>{o}</td></tr>" for c, e, o in rows)
            html += "</table>"
            report.extras = getattr(report, "extras", []) + [extras.html(html)]
        except Exception:
            for c, e, o in rows:
                report.user_properties.append((c, f"expected={e} observed={o}"))

    LOG_DIR.mkdir(exist_ok=True)
    name = item.nodeid.split("::")[-1].replace("[", "_").replace("]", "").replace("/", "_")
    with open(LOG_DIR / f"{name}.log", "w", encoding="utf-8") as f:
        f.write(f"TEST      : {item.nodeid}\n")
        f.write(f"OUTCOME   : {report.outcome.upper()}\n")
        f.write(f"DURATION  : {report.duration:.2f}s\n\n")
        if rows:
            f.write("EXPECTED vs OBSERVED\n")
            for c, e, o in rows:
                f.write(f"  - {c}: expected={e} | observed={o}\n")
            f.write("\n")
        for title, content in report.sections:
            f.write(f"--- {title} ---\n{content}\n")
        if report.longreprtext:
            f.write(f"\n--- failure ---\n{report.longreprtext}\n")
