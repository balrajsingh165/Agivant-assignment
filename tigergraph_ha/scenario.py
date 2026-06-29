"""End-to-end read- and write-path failure scenarios.

A scenario injects one fault, measures behaviour from a surviving node, recovers
the cluster, and writes results/<name>.json. The test suite calls these and
asserts on the returned metrics.
"""
import json
import os
import time
import urllib.request

from . import cluster, faults
from .probe import Probe, analyze

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_FAULT = {"kill": faults.kill, "stop": faults.stop, "pause": faults.pause, "partition": faults.partition}
_RECOVER = {"kill": faults.recover, "stop": faults.recover, "pause": faults.unpause, "partition": faults.heal}


def observer_for(target):
    """Return a node other than the fault target, used to observe availability."""
    return next(n for n in cluster.NODES if n != target)


def wait_healthy(url, timeout=180):
    """Block until url returns 200 or timeout; return the recovery time or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cluster.http_ok(url):
            return time.time()
        time.sleep(2)
    return None


def _save(name, result):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{name}.json"), "w") as f:
        json.dump(result, f, indent=2)


def _inject(action, target, service):
    if action == "component":
        faults.component_stop(target, service)
    else:
        _FAULT[action](target)


def _recover(action, target):
    if action == "component":
        cluster.gadmin("start all", timeout=300)
    else:
        _RECOVER[action](target)


def read_scenario(name, action, target, service=None, baseline=8, observe=25, recover_timeout=180):
    """Measure read availability and MTTR across a fault and recovery."""
    observer = observer_for(target)
    url = cluster.gateway_url(observer)
    probe = Probe(url).start()
    time.sleep(baseline)

    fault_ts = time.time()
    _inject(action, target, service)
    time.sleep(observe)
    _recover(action, target)

    recover_ts = wait_healthy(url, recover_timeout)
    time.sleep(4)
    probe.stop()

    res = analyze(probe.samples, fault_ts)
    res.update(scenario=name, fault=action, target=target, observer=observer,
               ha_mode=cluster.ha_mode(), recovered=recover_ts is not None)
    _save(name, res)
    return res


def _write_burst(observer, n, prefix):
    """Upsert n Person vertices through a node; return (succeeded, failed)."""
    url = cluster.gateway_url(observer, "/restpp/graph/social")
    ok = fail = 0
    for i in range(n):
        vid = f"{prefix}_{i}"
        body = json.dumps({"vertices": {"Person": {vid: {"name": {"value": vid}}}}}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=4) as r:
                error = json.loads(r.read()).get("error", True)
                ok += 0 if error else 1
                fail += 1 if error else 0
        except Exception:
            fail += 1
        time.sleep(0.1)
    return ok, fail


def write_scenario(name, action, target, n=40, recover_timeout=180):
    """Measure write availability and durability (no data loss) across a fault."""
    observer = observer_for(target)
    before = cluster.person_count(observer)

    _inject(action, target, None)
    time.sleep(4)
    ok, fail = _write_burst(observer, n, prefix=f"{name}_{int(before)}")
    _recover(action, target)
    wait_healthy(cluster.gateway_url(observer), recover_timeout)
    time.sleep(3)
    after = cluster.person_count(observer)

    # Durability invariant: every acknowledged write must persist, so the count
    # increase must be at least the acknowledged writes. An increase *greater*
    # than acknowledged is not data loss but write ambiguity (e.g. a request the
    # client saw time out under a partition that the server still committed).
    delta = (after - before) if (after is not None and before is not None) else None
    res = {
        "scenario": name, "ha_mode": cluster.ha_mode(), "fault": action, "target": target,
        "before": before, "after": after,
        "writes_attempted": n, "writes_ok": ok, "writes_failed": fail,
        "write_availability_pct": round(100 * ok / n, 1) if n else 0.0,
        "persisted_delta": delta,
        "ambiguous_writes": (delta - ok) if (delta is not None and delta > ok) else 0,
        "durable_no_loss": (delta is not None and delta >= ok),
    }
    _save(name, res)
    return res
