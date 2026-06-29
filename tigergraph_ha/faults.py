"""Node fault injection and recovery.

Each failure mode maps to a container or network operation; recovery restores the
node and restarts TigerGraph services. Used by the scenario runners.
"""
import time

from . import cluster
from .cluster import NETWORK, NODE_IP, docker_exec, gadmin, run


def kill(node):
    """Hard crash: the node disappears with no graceful shutdown."""
    run(["docker", "kill", node])


def stop(node):
    """Graceful shutdown of the node."""
    run(["docker", "stop", node])


def pause(node):
    """Freeze the node (up but unresponsive)."""
    run(["docker", "pause", node])


def unpause(node):
    """Resume a frozen node."""
    run(["docker", "unpause", node])


def partition(node):
    """Isolate the node from the cluster network."""
    run(["docker", "network", "disconnect", NETWORK, node])


def heal(node):
    """Reconnect an isolated node, restoring its original IP."""
    run(["docker", "network", "connect", "--ip", NODE_IP[node], NETWORK, node])


def component_stop(node, service):
    """Stop a single TigerGraph service on a node (e.g. GPE_2)."""
    docker_exec(node, f"export PATH=$PATH:{cluster.GADMIN_DIR}; gadmin stop {service} -y")


def is_running(node):
    """Return True when the container is running."""
    return run(["docker", "inspect", "-f", "{{.State.Running}}", node]).stdout.strip() == "true"


def recover(node):
    """Restore a failed node: start the container if down, then restart services."""
    if not is_running(node):
        run(["docker", "start", node])
        time.sleep(3)
    gadmin("start all", timeout=300)
