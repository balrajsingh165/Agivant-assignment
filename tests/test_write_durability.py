"""Write-path availability and durability under node failure.

While a node is down, vertices are upserted through a surviving node; after
recovery the suite verifies that every acknowledged write persisted (no data
loss). Under HA the write availability should additionally stay high.
"""
import pytest

from tigergraph_ha import scenario

CASES = [
    ("wkill_tg3", "kill", "tg3"),
    ("wpartition_tg2", "partition", "tg2"),
]


@pytest.mark.parametrize("name,action,target", CASES, ids=[c[0] for c in CASES])
def test_write_durability(name, action, target, ha_mode):
    """Writes acknowledged during an outage must still exist after recovery."""
    res = scenario.write_scenario(f"{ha_mode.lower()}_{name}", action, target)
    assert res["durable_no_loss"], f"data loss detected: {res}"
    if ha_mode == "HA":
        assert res["write_availability_pct"] >= 90, res
