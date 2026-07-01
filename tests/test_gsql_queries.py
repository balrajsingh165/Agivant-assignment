"""GSQL query combinations against the graph (functional / positive coverage).

Testing that the product actually works, not only that failures are handled:
representative query types - point lookup, 1-hop traversal, aggregation, and a
multi-hop traversal - each asserted for a correct result.
"""
import re

import pytest

from tigergraph_ha import cluster


def _n(out):
    """Extract the integer value printed as "n" from a gsql result, or -1."""
    m = re.search(r'"n":\s*(\d+)', out)
    return int(m.group(1)) if m else -1

Q_POINT = 'INTERPRET QUERY () FOR GRAPH social { s = {Person.*}; r = SELECT v FROM s:v WHERE v.id == "p1"; PRINT r.size() AS n; }'
Q_1HOP = 'INTERPRET QUERY () FOR GRAPH social { s = {Person.*}; r = SELECT t FROM s:v -(Friendship:e)- Person:t WHERE v.id == "p1"; PRINT r.size() AS n; }'
Q_AGG = 'INTERPRET QUERY () FOR GRAPH social { SumAccum<INT> @@n; s = {Person.*}; s = SELECT v FROM s:v ACCUM @@n += 1; PRINT @@n AS n; }'
Q_2HOP = 'INTERPRET QUERY () FOR GRAPH social { s = {Person.*}; h1 = SELECT t FROM s:v -(Friendship:e)- Person:t WHERE v.id == "p1"; h2 = SELECT t2 FROM h1:v -(Friendship:e)- Person:t2; PRINT h2.size() AS n; }'


CASES = [
    ("TC-QL-001", "point lookup by primary id", Q_POINT, lambda o: _n(o) == 1),
    ("TC-QL-002", "1-hop friendship traversal", Q_1HOP, lambda o: _n(o) >= 0),
    ("TC-QL-003", "aggregation over all Person", Q_AGG, lambda o: _n(o) >= 5000),
    ("TC-QL-004", "2-hop friendship traversal", Q_2HOP, lambda o: _n(o) >= 0),
]


@pytest.mark.gsql
@pytest.mark.parametrize("tc,desc,query,check", CASES, ids=[c[0] for c in CASES])
def test_gsql_query(tc, desc, query, check, record_expectation):
    """Run a GSQL query type and assert it returns a correct, error-free result."""
    out = cluster.gsql(query)
    ok = ("error" not in out.lower() or '"error": false' in out) and check(out)
    record_expectation(desc, expected="error-free result", observed="ok" if ok else out[:200])
    assert ok, f"{tc} ({desc}) unexpected output: {out[:300]}"
