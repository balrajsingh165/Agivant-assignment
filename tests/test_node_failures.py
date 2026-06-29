"""Read-path availability under representative node failures.

Each test injects one failure, measures recovery from a surviving node, saves a
results/<name>.json, and asserts on behaviour. HA-specific expectations apply
only when the license enables HA; otherwise the non-HA baseline is asserted.
"""
import pytest

from tigergraph_ha import scenario

# (id, fault action, target node, optional service)
CASES = [
    ("kill_tg2", "kill", "tg2", None),         # data node hard crash
    ("stop_tg2", "stop", "tg2", None),         # graceful shutdown
    ("pause_tg3", "pause", "tg3", None),       # frozen / unresponsive node
    ("partition_tg3", "partition", "tg3", None),  # network isolation
    ("component_gpe", "component", "tg2", "GPE_2"),  # single-component (GPE) failure
    ("kill_tg1", "kill", "tg1", None),         # master / gateway node crash
]


@pytest.mark.parametrize("name,action,target,service", CASES, ids=[c[0] for c in CASES])
def test_node_failure(name, action, target, service, ha_mode):
    """Inject a node failure and assert the cluster recovers within the timeout."""
    res = scenario.read_scenario(f"{ha_mode.lower()}_{name}", action, target, service=service)
    assert res["recovered"], f"{name}: cluster did not recover"
    if ha_mode == "HA":
        assert res["availability_pct"] >= 90, res  # replicas should keep serving
    else:
        assert res["mttr_s"] is not None, res       # baseline: an outage then recovery
