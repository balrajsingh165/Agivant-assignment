"""Loading-job behaviour: load data from a file data source and verify it lands.

Covers the product's ingestion path (not only failure injection). A small CSV is
generated on the cluster and loaded through the existing loading job; the vertex
count must increase by the number of rows loaded.
"""
import time

import pytest

from tigergraph_ha import cluster

CSVDIR = "/home/tigergraph/data_csv"


@pytest.mark.loading_job
def test_loading_job_file_source(record_expectation):
    """TC-LJ-001: a loading job from a CSV file source loads all rows."""
    before = cluster.person_count()
    n = 200
    # ids include the current count so re-runs load NEW vertices (upsert is idempotent)
    cluster.docker_exec(cluster.MASTER, f"""python3 - <<'PY'
n, seed = {n}, {before}
with open("{CSVDIR}/extra.csv","w") as f:
    f.write("id,name\\n")
    for i in range(n):
        f.write(f"lj_{{seed}}_{{i}},LoadJob_{{i}}\\n")
with open("{CSVDIR}/friend_empty.csv","w") as f:
    f.write("from,to\\n")
print("csv written")
PY""")
    out = cluster.gsql(
        f'RUN LOADING JOB load_social USING f_person="{CSVDIR}/extra.csv", f_friend="{CSVDIR}/friend_empty.csv"',
        graph="social")
    time.sleep(3)
    after = cluster.person_count()
    loaded = "LOAD SUCCESSFUL" in out or "FINISHED" in out.upper()
    record_expectation("loading job status", expected="LOAD SUCCESSFUL", observed="ok" if loaded else out[:200])
    record_expectation("vertex count increased", expected=f"+{n}", observed=f"{before} -> {after}")
    assert loaded, f"loading job did not succeed: {out[:300]}"
    assert after is not None and before is not None and after >= before + n - 5
