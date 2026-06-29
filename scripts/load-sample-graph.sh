#!/usr/bin/env bash
# Loads a small distributed social graph (Person + Friendship) into the cluster,
# then installs query endpoints used by the availability probe. Creating a schema
# also brings GPE/GSE from Warmup to Online.

set -euo pipefail
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'   # stop Git Bash mangling container paths
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

PERSONS="${1:-5000}"
FRIENDS="${2:-15000}"
CSVDIR=/home/tigergraph/data_csv

stamp "generating CSV ($PERSONS persons, $FRIENDS friendships)"
docker exec -i -u tigergraph "$MASTER" bash -lc "mkdir -p $CSVDIR"
docker exec -i -u tigergraph "$MASTER" python3 - "$PERSONS" "$FRIENDS" <<'PY'
import sys
n, m = int(sys.argv[1]), int(sys.argv[2])
d = "/home/tigergraph/data_csv"
with open(f"{d}/persons.csv", "w") as f:
    f.write("id,name\n")
    for i in range(n):
        f.write(f"p{i},Person_{i}\n")
with open(f"{d}/friendships.csv", "w") as f:
    f.write("from,to\n")
    for i in range(m):                       # ring + chords so every partition holds data
        f.write(f"p{i % n},p{(i * 7 + 1) % n}\n")
print("csv written")
PY

for f in schema load queries; do
  docker exec -i -u tigergraph "$MASTER" bash -lc "cat > $CSVDIR/$f.gsql" < "$HERE/sample-graph/$f.gsql"
done
docker exec -i -u tigergraph "$MASTER" bash -lc "chown -R tigergraph:tigergraph $CSVDIR"

stamp "creating schema"
tg_exec "$MASTER" "gsql $CSVDIR/schema.gsql"
stamp "loading data"
tg_exec "$MASTER" "gsql $CSVDIR/load.gsql"
stamp "installing queries"
tg_exec "$MASTER" "gsql $CSVDIR/queries.gsql"

stamp "done; GPE/GSE status:"
gadmin "status -v" | grep -E "GPE|GSE" || true
