# Test Plan — TigerGraph HA Node-Failure

Browsable version of `TestPlan.xlsx` / `TestPlan.pdf`. Columns follow the required
format: **Test Case ID | Type | Description | Precondition | Input/Test Steps |
Base URL & API**. Manual→automation mapping is in `TraceabilityMatrix.xlsx`;
measured results in `REPORT.md` and `results/`.

`ping_count` below = `GET http://localhost:14240/restpp/query/social/ping_count`.

## Functional (positive)

| Test Case ID | Type | Description | Precondition | Input/Test Steps | Base URL & API |
|---|---|---|---|---|---|
| TC-QL-001 | Positive | Point lookup: query a Person by primary id returns one vertex. | HA cluster active; graph loaded. | 1. Open gsql on graph social 2. Run point lookup for id p1 3. Verify one vertex | `gsql -g social 'INTERPRET QUERY(){ ... WHERE v.id=="p1" }'` |
| TC-QL-002 | Positive | 1-hop traversal: friends of a Person are returned. | HA cluster active; graph loaded. | 1. Open gsql 2. 1-hop Friendship traversal from p1 3. Verify neighbours | `gsql -g social 'INTERPRET QUERY(){ -(Friendship)- Person }'` |
| TC-QL-003 | Positive | Aggregation: count of all Person vertices (≥ base 5000). | HA cluster active; graph loaded. | 1. Open gsql 2. SumAccum count over Person 3. Verify count ≥ 5000 | `gsql -g social 'INTERPRET QUERY(){ ACCUM @@n+=1 }'` |
| TC-QL-004 | Positive | Multi-hop: 2-hop friendship expansion returns a result. | HA cluster active; graph loaded. | 1. Open gsql 2. 2-hop traversal from p1 3. Verify non-empty | `gsql -g social 'INTERPRET QUERY(){ 2-hop }'` |
| TC-SV-001 | Positive | Service health: all critical services (GPE/GSE/RESTPP/GSQL) Online. | HA cluster active. | 1. `gadmin status -v` 2. Parse states 3. Verify all Online | `gadmin status -v` |
| TC-LJ-001 | Positive | Loading job: load Person rows from a CSV file source; count increases. | HA cluster active; job defined. | 1. Generate CSV (200 rows) 2. RUN LOADING JOB 3. Verify LOAD SUCCESSFUL and count +200 | `gsql -g social 'RUN LOADING JOB load_social USING f_person="...csv"'` |

## Behaviour under node failure

| Test Case ID | Type | Description | Precondition | Input/Test Steps | Base URL & API |
|---|---|---|---|---|---|
| TC-NF-001 | Failure | Data-node hard crash; measure availability + MTTR. | HA active; probe running. | 1. Start probe 2. `docker kill tg2` 3. Observe 4. Recover | `docker kill tg2` ; ping_count |
| TC-NF-002 | Failure | Graceful node shutdown; measure recovery. | HA active; probe running. | 1. Start probe 2. `docker stop tg2` 3. Observe 4. Recover | `docker stop tg2` ; ping_count |
| TC-NF-003 | Failure | Frozen node (up but unresponsive); measure recovery. | HA active; probe running. | 1. Start probe 2. `docker pause tg3` 3. Observe 4. Unpause | `docker pause tg3` ; ping_count |
| TC-NF-004 | Failure | Network partition; measure rejoin behaviour. | HA active; probe running. | 1. Start probe 2. Disconnect tg3 3. Observe 4. Reconnect | `docker network disconnect tgnet tg3` ; ping_count |
| TC-NF-005 | Failure | Single-component (GPE) failure; measure behaviour. | HA active; probe running. | 1. Start probe 2. `gadmin stop GPE_1#2` 3. Observe 4. Restart | `gadmin stop GPE` ; ping_count |
| TC-NF-006 | Failure | Master/gateway-node crash; observe from a surviving node. | HA active; probe on tg2. | 1. Probe tg2 gateway 2. `docker kill tg1` 3. Observe 4. Recover | `docker kill tg1` ; `http://localhost:14241/...` |
| TC-SV-002 | Failure | Service crash on node loss: killed node's GPE/GSE/RESTPP go down; a replica stays Online. | HA active. | 1. Baseline status 2. `docker kill tg2` 3. `gadmin status -v` 4. Verify | `docker kill tg2` ; `gadmin status -v` |
| TC-WR-001 | Failure | Write durability under crash: acknowledged writes not lost. | HA active. | 1. Record count 2. `docker kill tg3` 3. Upsert N 4. Recover; verify | `docker kill tg3` ; `POST .../restpp/graph/social` |
| TC-WR-002 | Failure | Write durability under partition: ambiguous writes; nothing acknowledged lost. | HA active. | 1. Record count 2. Partition tg2 3. Upsert N 4. Heal; verify | `network disconnect tg2` ; `POST .../restpp/graph/social` |

## Negative & boundary

| Test Case ID | Type | Description | Precondition | Input/Test Steps | Base URL & API |
|---|---|---|---|---|---|
| TC-NG-001 | Negative | Invalid query is rejected gracefully; cluster keeps serving. | HA active. | 1. Run invalid GSQL 2. Verify error returned 3. Verify gateway still serves | `gsql -g social '<invalid>'` ; ping_count |
| TC-BD-001 | Boundary | Two-node failure exceeds RF=2 tolerance; cluster recovers after nodes return. | HA active. | 1. `docker kill tg2 tg3` 2. Observe availability 3. Recover both 4. Verify recovery | `docker kill tg2 tg3` ; ping_count |
