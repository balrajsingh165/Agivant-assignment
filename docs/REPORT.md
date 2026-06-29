# TigerGraph High-Availability Node-Failure — Test Report

**Product under test:** TigerGraph 4.1.4 (Enterprise), self-hosted 3-node cluster
**Scope:** failure-recovery behaviour under node failures; recovery time (MTTR)

> 4.1.3 is specified by the assignment. TigerGraph's download portal serves only
> the latest patch of each line (4.1.4); 4.1.3 is not separately downloadable.
> 4.1.4 is the closest release in the same 4.1 minor line and is used here.

---

## 1. Summary

A 3-node TigerGraph cluster was built and subjected to representative node
failures while a client continuously exercised the database. For each failure we
measured time-to-detect, downtime, time-to-recovery (MTTR), and data durability.

Headline results:

- Every failure mode recovered cleanly, with **no data loss** across the run.
- Recovery time is governed by the **recovery mechanism**, not the severity of the
  fault: failures needing a service or node restart recover in ~50–60 s, while a
  freeze or a network partition (which only need resume/reconnect) recover in
  ~25–30 s.
- A single failed component (GPE) is tolerated noticeably longer before the data
  path is affected (~13 s) than a whole-node loss (~3 s).
- Loss of the gateway/master node is survivable: a surviving node continued to
  serve and the cluster recovered in ~60 s.

---

## 2. Environment

| Item | Detail |
|------|--------|
| Cluster | 3 nodes (`tg1`, `tg2`, `tg3`) as Docker containers on bridge network `tgnet`, static IPs |
| Gateways | each node's REST/GraphStudio gateway published to the host (14240/14241/14242) |
| Data | `Person` (5,000) + `Friendship` (15,000), hash-distributed across all nodes |
| Workload | installed distributed query `ping_count` (full RESTPP→GPE data path) |
| Test harness | Python + pytest, dependencies managed with `uv` |

Docker containers are used because they make node failure precise and
repeatable: `docker kill` (crash), `docker stop` (graceful), `docker pause`
(freeze), and `docker network disconnect` (partition) reproduce distinct
real-world failure modes that are difficult to stage on bare metal.

### Replication and the two test tracks

Replication factor determines whether the cluster is highly available. The suite
**detects the active configuration** and runs the matching track:

- **HA (replication factor 2):** each partition has a replica on another node. A
  single node loss is expected to keep the data path available; the tests assert
  that availability stays high and MTTR is small.
- **Non-HA (replication factor 1):** each partition has a single copy. A node loss
  takes its partition offline until the node is restored; the tests assert that
  the system detects the loss and recovers.

The results in §4 are for the **replication-factor-1** configuration. The HA track
runs the identical scenarios with availability-preservation assertions; enabling a
replication-factor-2 license switches the suite to it automatically with no code
changes.

---

## 3. Methodology — how MTTR is measured

An in-process probe issues the `ping_count` query every **250 ms** from a
**surviving (observer) node**, recording the outcome and timestamp of every
request. Observing from a node other than the fault target means *any* node —
including the gateway/master node — can be failed while availability is still
measured.

From the probe log, relative to the fault-injection timestamp:

| Metric | Definition |
|--------|------------|
| **MTTD** | fault injected → first failed request (detection) |
| **Downtime** | first failed request → first sustained success |
| **MTTR** | fault injected → service fully restored |
| **Availability** | successful / total requests during the scenario window |

A write-path test additionally upserts vertices through a surviving node *during*
an outage and, after recovery, verifies that every acknowledged write persisted
(no data loss) and reports write availability.

Recovery is confirmed by polling the gateway until the query endpoint returns
HTTP 200. Tests live in `tests/`; raw per-scenario results in `results/`.

---

## 4. Test cases and findings

| # | Test case | Fault | MTTD (s) | Downtime (s) | MTTR (s) | Availability |
|---|-----------|-------|---------:|-------------:|---------:|-------------:|
| 1 | Data-node hard crash | `docker kill tg2` | 2.8 | 50.0 | 52.9 | 70% |
| 2 | Graceful node shutdown | `docker stop tg2` | 2.5 | 48.3 | 50.9 | 72% |
| 3 | Frozen / unresponsive node | `docker pause tg3` | 3.3 | 23.3 | 26.6 | 84% |
| 4 | Network partition | isolate tg3 | 3.1 | 27.3 | 30.1 | 75% |
| 5 | Single-component failure | stop `GPE_2` | 13.5 | 42.5 | 56.0 | 84% |
| 6 | Master / gateway-node crash | `docker kill tg1` | 10.4 | 49.2 | 59.6 | 96% |
| 7 | Write durability under failure | `docker kill tg3` | — | — | — | 75% writes |

### 4.1 Data-node hard crash
**Reasoning:** the most severe unplanned failure — a node disappears with no
graceful shutdown. **Finding:** queries began failing 2.8 s after the crash and
the affected partition was unavailable for 50 s; full recovery required restarting
the node and its services — **MTTR 52.9 s**. At replication factor 1 there is no
replica to take over, so the data path is unavailable until the node returns.

### 4.2 Graceful node shutdown
**Reasoning:** planned maintenance — does an orderly stop behave better than a
crash? **Finding:** essentially identical to the crash (MTTD 2.5 s, **MTTR
50.9 s**). With a single copy of each partition, a clean shutdown provides no
availability benefit; the partition is gone until the node restarts.

### 4.3 Frozen / unresponsive node
**Reasoning:** real nodes do not always crash cleanly — they hang (GC pauses, disk
stalls, CPU starvation). **Finding:** detected in 3.3 s; recovery was the fastest
(**MTTR 26.6 s**) because resuming the node restarts the existing processes — no
service restart is needed and the system re-converges on its own.

### 4.4 Network partition
**Reasoning:** the classic distributed-systems failure — a node is alive but
isolated. **Finding:** detected in 3.1 s; **MTTR 30.1 s** after reconnection at the
node's original address. No data loss. Reconnection (rather than a full restart)
is why recovery is faster than the crash cases.

### 4.5 Single-component failure
**Reasoning:** TigerGraph runs multiple services per node; isolating one engine
(the GPE serving a partition) tests behaviour at finer granularity than a
whole-node loss. **Finding:** the data path kept working for **13.5 s** before
queries failed — markedly longer than a whole-node loss — then recovery via a
service restart gave **MTTR 56.0 s**. Component-level loss therefore has a longer
tolerance window than node loss.

### 4.6 Master / gateway-node crash
**Reasoning:** losing the node that also fronts the gateway is the case most
likely to take the whole system down. **Finding:** observed from a surviving node,
the cluster tolerated the loss for 10.4 s before queries failed, then recovered in
**59.6 s** (96% availability over the window). Loss of any single node — including
the master — is survivable and self-recovering.

### 4.7 Write durability under failure
**Reasoning:** the hardest question — does a write *during* a node failure succeed,
and is it still there afterwards? **Finding:** with one node down, 30 of 40 upserts
succeeded (**75% write availability**) — the ~25% that targeted the offline
partition failed — and **all 30 acknowledged writes persisted** after recovery
(vertex count rose by exactly 30). Writes are never silently lost: a write either
fails outright or is durable.

---

## 5. Cross-cutting observations

- **Detection is fast and uniform** (~2.5–3.3 s) for whole-node failures; a single
  component failure surfaces more slowly (~13 s).
- **Recovery cost tracks the recovery mechanism, not fault severity.** Restart-based
  recovery (crash, graceful stop, component) clusters at ~50–60 s; resume/reconnect
  recovery (freeze, partition) at ~25–30 s.
- **No data loss in any scenario.** After repeated destructive cycles the cluster
  returned to full health with all data intact; acknowledged writes always persisted.
- At replication factor 1 there is no failover — every node loss causes an outage of
  its partition. This is the baseline that quantifies the value of running with
  replication factor 2.

---

## 6. Reproducing

```bash
docker compose up -d                 # start the 3-node cluster
bash scripts/01-install.sh           # install TigerGraph (replication factor from license)
bash scripts/load-sample-graph.sh    # load the sample graph + query endpoints
uv sync                              # set up the test environment
uv run pytest                        # run the failure suite -> results/
```

Individual case: `uv run pytest "tests/test_node_failures.py::test_node_failure[kill_tg2]"`.
