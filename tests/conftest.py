"""Shared fixtures: confirm the cluster is reachable and the sample graph loaded."""
import sys
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
