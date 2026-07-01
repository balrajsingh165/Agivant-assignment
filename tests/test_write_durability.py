"""Write-path availability and durability under node failure.

While a node is down, vertices are upserted through a surviving node; after
recovery the state is checked. A clean node crash must not lose acknowledged
writes (strict). A network partition is inherently ambiguous - writes may be
acknowledged by the majority yet reconcile with a delay (eventual consistency,
see docs/findings/FIND-002) - so there we assert recovery to a consistent,
serving state and record the write outcome rather than assert strict durability.
"""
import pytest

from tigergraph_ha import cluster, scenario

# (TC id, fault action, target node, result name, strict durability)
CASES = [
    ("TC-WR-001", "kill", "tg3", "wkill_tg3", True),
    ("TC-WR-002", "partition", "tg2", "wpartition_tg2", False),
]


@pytest.mark.write_durability
@pytest.mark.parametrize("tc,action,target,name,strict", CASES, ids=[c[0] for c in CASES])
def test_write_durability(tc, action, target, name, strict, ha_mode, record_expectation):
    """Writes during a node loss: no loss under a clean crash; consistent recovery under a partition."""
    res = scenario.write_scenario(f"{ha_mode.lower()}_{name}", action, target)

    record_expectation("write availability %", expected="writes to live replicas succeed",
                       observed=res["write_availability_pct"])
    record_expectation("acknowledged writes persisted (delta >= ok)",
                       expected="True (clean crash)" if strict else "eventual/ambiguous (partition)",
                       observed=res["durable_no_loss"])

    # In all cases the cluster must return to a consistent, serving state.
    assert res["after"] is not None, "vertex count not readable after recovery"
    assert cluster.http_ok(cluster.gateway_url()), "cluster not serving after recovery"

    if strict:
        assert res["durable_no_loss"], f"data loss under a clean crash: {res}"
        if ha_mode == "HA":
            assert res["write_availability_pct"] >= 80, res
