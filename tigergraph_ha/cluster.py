"""Cluster access: docker, gadmin, gateway endpoints, and HA detection.

All external calls go through subprocess (native process creation) and the
standard library, so the harness runs the same on Windows, Linux and macOS.
"""
import json
import re
import subprocess
import urllib.request

NODES = ["tg1", "tg2", "tg3"]
MASTER = "tg1"
NETWORK = "tgnet"
GADMIN_DIR = "/home/tigergraph/tigergraph/app/cmd"
NODE_IP = {"tg1": "172.20.0.11", "tg2": "172.20.0.12", "tg3": "172.20.0.13"}
GATEWAY_PORT = {"tg1": 14240, "tg2": 14241, "tg3": 14242}
QUERY_PATH = "/restpp/query/social/ping_count"


def run(args, timeout=60):
    """Run a command and return its CompletedProcess (never raises on nonzero)."""
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def docker_exec(node, command, user="tigergraph", timeout=120):
    """Run a shell command inside a node as the given user."""
    return run(["docker", "exec", "-u", user, "-e", "TERM=dumb", node, "bash", "-lc", command], timeout=timeout)


def gadmin(args, timeout=180):
    """Run a gadmin command on the master node."""
    return docker_exec(MASTER, f"export PATH=$PATH:{GADMIN_DIR}; gadmin {args}", timeout=timeout)


def ha_licensed():
    """Return True when the active license enables Data HA (replication factor > 1)."""
    out = gadmin("license status").stdout
    m = re.search(r"DataHA:.*?Enable:\s*(\w+)", out, re.S)
    return bool(m) and m.group(1).lower() == "true"


def ha_mode():
    """Return 'HA' when HA is licensed, otherwise 'NOHA'."""
    return "HA" if ha_licensed() else "NOHA"


def gateway_url(node=MASTER, path=QUERY_PATH):
    """Host URL for a node's published gateway."""
    return f"http://localhost:{GATEWAY_PORT[node]}{path}"


def http_ok(url, timeout=3):
    """Return True when GET url responds with a 2xx status."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def person_count(node=MASTER):
    """Return the Person vertex count via the ping_count query, or None on failure."""
    try:
        with urllib.request.urlopen(gateway_url(node), timeout=6) as r:
            return json.loads(r.read())["results"][0]["person_count"]
    except Exception:
        return None


def gsql(command, graph="social", timeout=180):
    """Run a GSQL command/query on the master; return stdout."""
    g = f"-g {graph} " if graph else ""
    esc = command.replace("'", "'\\''")
    return docker_exec(MASTER, f"export PATH=$PATH:{GADMIN_DIR}; gsql {g}'{esc}'", timeout=timeout).stdout


def service_states(node=MASTER):
    """Parse `gadmin status -v` into {service_name: status} (e.g. GPE_1#1 -> Online)."""
    states = {}
    for line in gadmin("status -v").stdout.splitlines():
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2 and cells[1] in ("Online", "Offline", "Warmup", "Down", "Stopped"):
            states[cells[0]] = cells[1]
    return states
