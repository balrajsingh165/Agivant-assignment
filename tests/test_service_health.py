"""Service-health behaviour: are GPE/GSE/RESTPP up, and do they go down on a node loss?

Directly addresses the review point - when a node is killed, which internal
services crash/go down. Uses `gadmin status` to inspect service state.
"""
import time

import pytest

from tigergraph_ha import cluster, faults

CRITICAL = ("GPE", "GSE", "RESTPP", "GSQL")


@pytest.mark.service_health
def test_all_services_online(record_expectation):
    """TC-SV-001: on a healthy HA cluster all critical services are Online."""
    crit = {}
    for _ in range(20):
        states = cluster.service_states()
        crit = {k: v for k, v in states.items() if any(k.startswith(c) for c in CRITICAL)}
        if crit and all(v == "Online" for v in crit.values()):
            break
        time.sleep(6)
    online = [k for k, v in crit.items() if v == "Online"]
    record_expectation("all critical services Online", expected="all Online",
                       observed=f"{len(online)}/{len(crit)} Online")
    assert crit and all(v == "Online" for v in crit.values()), crit


@pytest.mark.service_health
def test_services_down_on_node_kill(record_expectation):
    """TC-SV-002: killing a node takes that node's service instances down; peers stay Online."""
    before = cluster.service_states()
    faults.kill("tg2")
    try:
        time.sleep(12)
        during = cluster.service_states()
        down = [k for k, v in during.items() if v not in ("Online", "Warmup")]
        peers_online = any(v == "Online" for k, v in during.items() if k.startswith("GPE"))
        record_expectation("killed node's services go down", expected=">0 services down",
                           observed=f"{len(down)} down: {down[:6]}")
        record_expectation("a GPE replica stays Online (HA)", expected="True", observed=str(peers_online))
        assert len(down) > 0, "expected some services to drop after node kill"
        assert peers_online, "expected a surviving GPE replica to remain Online"
    finally:
        faults.recover("tg2")
        for _ in range(30):
            if cluster.http_ok(cluster.gateway_url()):
                break
            time.sleep(3)
