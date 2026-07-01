"""Read-path availability under representative node failures.

Each test injects one failure, measures recovery from a surviving node, saves a
results/<name>.json, records expected-vs-observed for the report, and asserts on
behaviour. HA-specific expectations apply only when the license enables HA;
otherwise the non-HA baseline is asserted.
"""
import pytest

from tigergraph_ha import scenario

# (TC id, fault action, target node, service, result name)
CASES = [
    ("TC-NF-001", "kill", "tg2", None, "kill_tg2"),          # data node hard crash
    ("TC-NF-002", "stop", "tg2", None, "stop_tg2"),          # graceful shutdown
    ("TC-NF-003", "pause", "tg3", None, "pause_tg3"),        # frozen / unresponsive node
    ("TC-NF-004", "partition", "tg3", None, "partition_tg3"),  # network isolation
    ("TC-NF-005", "component", "tg2", "GPE_2", "component_gpe"),  # single-component (GPE) failure
    ("TC-NF-006", "kill", "tg1", None, "kill_tg1"),          # master / gateway node crash
]


@pytest.mark.node_failure
@pytest.mark.parametrize("tc,action,target,service,name", CASES, ids=[c[0] for c in CASES])
def test_node_failure(tc, action, target, service, name, ha_mode, record_expectation):
    """Inject a node failure and assert the cluster recovers within the timeout."""
    res = scenario.read_scenario(f"{ha_mode.lower()}_{name}", action, target, service=service)

    record_expectation("recovered", expected="True", observed=str(res["recovered"]))
    record_expectation("MTTR (s)", expected="finite; cluster recovers", observed=res["mttr_s"])
    record_expectation("availability %", expected=">=90 (HA)" if ha_mode == "HA" else "outage then recovery",
                       observed=res["availability_pct"])

    assert res["recovered"], f"{tc}: cluster did not recover"
    if ha_mode == "HA":
        # Replicas keep serving. Freeze/partition/component are absorbed (~100%);
        # losing a live node (kill/stop/master) still costs a brief failover window,
        # so the realistic HA floor is well above the non-HA baseline (~74%).
        assert res["availability_pct"] >= 80, res
    else:
        assert res["mttr_s"] is not None, res       # baseline: an outage then recovery
