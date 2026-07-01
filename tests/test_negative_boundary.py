"""Negative and boundary coverage around node failures.

Negative: an invalid query is rejected gracefully (no crash). Boundary: killing
two of three nodes exceeds the replication factor's single-node tolerance; the
cluster must still recover once the nodes return.
"""
import time

import pytest

from tigergraph_ha import cluster, faults


@pytest.mark.negative
def test_invalid_query_rejected(record_expectation):
    """TC-NG-001: an invalid GSQL query returns an error and does not crash the cluster."""
    out = cluster.gsql('INTERPRET QUERY () FOR GRAPH social { THIS IS NOT VALID GSQL }')
    rejected = any(k in out.lower() for k in ("error", "syntax", "encountered", "fail"))
    still_up = cluster.http_ok(cluster.gateway_url())
    record_expectation("invalid query rejected", expected="error reported", observed="rejected" if rejected else out[:150])
    record_expectation("cluster still serving after bad query", expected="True", observed=str(still_up))
    assert rejected and still_up


@pytest.mark.boundary
def test_two_node_failure_boundary(record_expectation):
    """TC-BD-001: killing two of three nodes exceeds RF=2 tolerance; cluster recovers after."""
    faults.kill("tg2")
    faults.kill("tg3")
    try:
        time.sleep(10)
        available = cluster.http_ok(cluster.gateway_url(), timeout=5)
        record_expectation("availability with 2/3 nodes down", expected="likely lost (exceeds RF=2)",
                           observed="serving" if available else "unavailable")
    finally:
        for n in ("tg2", "tg3"):
            faults.recover(n)
        recovered = False
        for _ in range(40):
            if cluster.http_ok(cluster.gateway_url()):
                recovered = True
                break
            time.sleep(3)
    record_expectation("cluster recovers after both nodes return", expected="True", observed=str(recovered))
    assert recovered, "cluster did not recover after the two-node failure"
