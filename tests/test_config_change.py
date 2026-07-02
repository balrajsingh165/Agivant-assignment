"""Configuration-change behaviour: change a service config, restart, verify it applies and recovers.

This is not failure injection - it exercises TigerGraph's configuration management
and restart resilience: stage a gadmin config change, apply it, restart all
services, then confirm the new value took effect and every service returned Online.
The change is reverted afterwards so the cluster is left at its baseline.
"""
import time

import pytest

from tigergraph_ha import cluster

# A safe, service-level RESTPP setting (query timeout, seconds); the change is reversible.
VAR = "RESTPP.Factory.DefaultQueryTimeoutSec"
CRITICAL = ("GPE", "GSE", "RESTPP", "GSQL")


def _wait_serving(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cluster.http_ok(cluster.gateway_url(), timeout=4):
            return True
        time.sleep(6)
    return False


@pytest.mark.config
def test_config_change_and_restart(record_expectation):
    """TC-CFG-001: change a service config var, apply + restart all, verify applied and services recover."""
    original = cluster.config_get(VAR).strip() or "16"
    new_val = "45" if original != "45" else "30"
    try:
        cluster.config_set(VAR, new_val)
        cluster.config_apply()
        cluster.restart_all()
        assert _wait_serving(), "cluster did not return to serving after config restart"

        # after restart-all, services return gradually (Warmup -> Online); wait for all critical Online
        crit = {}
        for _ in range(30):
            states = cluster.service_states()
            crit = {k: v for k, v in states.items() if any(k.startswith(c) for c in CRITICAL)}
            if crit and all(v == "Online" for v in crit.values()):
                break
            time.sleep(6)
        all_online = bool(crit) and all(v == "Online" for v in crit.values())
        applied = cluster.config_get(VAR).strip()

        record_expectation("config value applied after restart", expected=new_val, observed=applied)
        record_expectation("all critical services Online after restart", expected="True", observed=str(all_online))
        record_expectation("query serves after config restart", expected="200",
                           observed="200" if cluster.http_ok(cluster.gateway_url()) else "down")
        assert new_val == applied, f"config not applied (got {applied!r})"
        assert all_online, crit
    finally:
        cluster.config_set(VAR, original)
        cluster.config_apply()
        cluster.restart_all()
        _wait_serving()
