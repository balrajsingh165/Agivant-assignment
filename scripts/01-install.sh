#!/usr/bin/env bash
# Installs TigerGraph across the 3-node cluster. The replication factor is chosen
# automatically from the license: RF=2 when the license enables Data HA, else
# RF=1 (non-HA). Assumes `docker compose up -d` has been run.
#
# Inputs (host paths):
#   TG_TARBALL  path to tigergraph-*-offline.tar.gz   (default: ~/Downloads/...)
#   TG_LICENSE  path to license.txt                   (default: ~/Downloads/license.txt)

set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

TG_TARBALL="${TG_TARBALL:-$HOME/Downloads/tigergraph-4.1.4-offline.tar.gz}"
TG_LICENSE="${TG_LICENSE:-$HOME/Downloads/license.txt}"
HOME_TG=/home/tigergraph

stamp "ensuring prerequisites (uuid-runtime) on all nodes"
for n in "${NODES[@]}"; do
  docker exec "$n" bash -lc 'command -v uuidgen >/dev/null || (apt-get update -qq && apt-get install -y -qq uuid-runtime)' >/dev/null 2>&1
done

stamp "copying license + tarball into $MASTER"
docker exec -i -u tigergraph "$MASTER" bash -lc "cat > $HOME_TG/license.txt" < "$TG_LICENSE"
docker exec -i -u tigergraph "$MASTER" bash -lc "cat > $HOME_TG/tg-offline.tar.gz" < "$TG_TARBALL"
docker exec -u tigergraph "$MASTER" bash -lc "cd $HOME_TG && rm -rf tigergraph-*-offline && tar -xzf tg-offline.tar.gz && chown -R tigergraph:tigergraph $HOME_TG"
INSTDIR="$(docker exec -u tigergraph "$MASTER" bash -lc "ls -d $HOME_TG/tigergraph-*-offline | head -1" | tr -d '\r')"

stamp "selecting replication factor from license DataHA entitlement"
RF="$(docker exec -i -u tigergraph "$MASTER" python3 - <<'PY'
import base64, json
seg = open('/home/tigergraph/license.txt').read().strip().split('.')[1]
seg += '=' * (-len(seg) % 4)
d = json.loads(base64.urlsafe_b64decode(seg))
print(2 if d.get('DataHA', {}).get('Enable') else 1)
PY
)"
echo "    -> ReplicationFactor=$RF ($([ "$RF" = 2 ] && echo HA || echo non-HA))"

stamp "generating install_conf.json"
docker exec -i -u tigergraph "$MASTER" python3 - "$INSTDIR" "$RF" "${NODE_IP[tg1]}" "${NODE_IP[tg2]}" "${NODE_IP[tg3]}" <<'PY'
import json, sys
inst, rf, ip1, ip2, ip3 = sys.argv[1], int(sys.argv[2]), *sys.argv[3:6]
lic = open('/home/tigergraph/license.txt').read().strip()
conf = {
  "BasicConfig": {
    "TigerGraph": {"Username": "tigergraph", "Password": "tigergraph", "SSHPort": 22, "PrivateKeyFile": "", "PublicKeyFile": ""},
    "RootDir": {"AppRoot": "/home/tigergraph/tigergraph/app", "DataRoot": "/home/tigergraph/tigergraph/data",
                 "LogRoot": "/home/tigergraph/tigergraph/log", "TempRoot": "/home/tigergraph/tigergraph/tmp"},
    "License": lic, "RegionAware": False,
    "NodeList": [f"m1: {ip1}", f"m2: {ip2}", f"m3: {ip3}"],
  },
  "AdvancedConfig": {"ClusterConfig": {
    "LoginConfig": {"SudoUser": "tigergraph", "Method": "K", "K": "/home/tigergraph/.ssh/id_rsa"},
    "ReplicationFactor": rf}},
}
json.dump(conf, open(f"{inst}/install_conf.json", "w"), indent=2)
print("written", f"{inst}/install_conf.json")
PY

stamp "running installer (uninstall any prior install first)"
docker exec -u tigergraph -e TERM=dumb "$MASTER" bash -lc "
  export PATH=\$PATH:$GADMIN_DIR
  guninstall -y 2>/dev/null || true
  cd $INSTDIR && ./install.sh -n"

stamp "install done; status:"
gadmin "status -v" | grep -E "GPE|GSE|RESTPP|HA mode" || true
echo "HA mode: $(ha_mode)"
