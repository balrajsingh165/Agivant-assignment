#!/usr/bin/env bash
# Shared helpers for the TigerGraph HA test scripts.
# Defines the node set, gadmin access, timestamp markers, and HA auto-detection.
# The HA detection lets the suite adapt: full failover tests when the license
# enables Data HA, otherwise a non-HA baseline run.

set -euo pipefail

NODES=(tg1 tg2 tg3)
MASTER=tg1
NETWORK=tgnet
GADMIN_DIR=/home/tigergraph/tigergraph/app/cmd

# Install-time IPs (the cluster was configured with these). Heal after a network
# partition must restore the exact IP or the node rejoins with the wrong address.
declare -A NODE_IP=( [tg1]=172.20.0.11 [tg2]=172.20.0.12 [tg3]=172.20.0.13 )

# tg_exec <node> <cmd...> : run a command as the tigergraph user inside a node.
tg_exec() {
  local node="$1"; shift
  docker exec -u tigergraph -e TERM=dumb "$node" bash -lc "export PATH=\$PATH:$GADMIN_DIR; $*"
}

# gadmin <args...> : run gadmin on the master node.
gadmin() { tg_exec "$MASTER" "gadmin $*"; }

# ts : current epoch seconds (used to correlate fault injection with probe windows).
ts() { date +%s; }

# stamp <msg> : print an epoch-stamped marker for the test log.
stamp() { echo "[$(ts)] $(date '+%H:%M:%S') $*"; }

# ha_licensed : succeed (0) if the active license enables Data HA.
ha_licensed() {
  gadmin license status 2>/dev/null \
    | awk '/DataHA:/{f=1} f&&/Enable:/{print; exit}' \
    | grep -qi 'true'
}

# cluster_rf : print the configured replication factor (best-effort).
cluster_rf() {
  gadmin config get System.HAStandbyReplica 2>/dev/null \
    || gadmin config dump 2>/dev/null | awk '/"Replica":/{print $2}' | sort -un | tail -1
}

# ha_mode : echo "HA" when failover testing is possible, else "NOHA".
ha_mode() {
  if ha_licensed; then echo HA; else echo NOHA; fi
}
