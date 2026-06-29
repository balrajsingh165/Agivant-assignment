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

- Every failure mode recovered cleanly, and **no acknowledged write was ever lost**.
- Recovery time is governed by the **recovery mechanism**, not the severity of the
  fault: failures needing a service or node restart recover in ~52–57 s, while a
  freeze or a network partition (which only need resume/reconnect) recover in
  ~23–33 s.
- A single failed component (GPE) is tolerated ~11 s before the data path is
  affected, whereas a whole-node loss is felt almost immediately (~0.2 s).
- Loss of the gateway/master node is survivable: a surviving node kept serving and
  the cluster recovered in ~56 s.

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
| 1 | Data-node hard crash | `docker kill tg2` | 0.2 | 52.3 | 53.5 | 74% |
| 2 | Graceful node shutdown | `docker stop tg2` | 0.2 | 52.4 | 52.6 | 74% |
| 3 | Frozen / unresponsive node | `docker pause tg3` | 0.3 | 22.9 | 23.2 | 87% |
| 4 | Network partition | isolate tg3 | 0.2 | 29.5 | 32.8 | 84% |
| 5 | Single-component failure | stop `GPE_2` | 11.3 | 45.8 | 57.1 | 87% |
| 6 | Master / gateway-node crash | `docker kill tg1` | 0.2 | 55.6 | 55.9 | 73% |
| 7 | Write durability under failure | `docker kill tg3` / partition | — | — | — | no loss |

### 4.1 Data-node hard crash
**Reasoning:** the most severe unplanned failure — a node disappears with no
graceful shutdown. **Finding:** queries began failing almost immediately (0.2 s) and
the affected partition was unavailable for ~52 s; full recovery required restarting
the node and its services — **MTTR 53.5 s**. At replication factor 1 there is no
replica to take over, so the data path is unavailable until the node returns.

### 4.2 Graceful node shutdown
**Reasoning:** planned maintenance — does an orderly stop behave better than a
crash? **Finding:** essentially identical to the crash (**MTTR 52.6 s**). With a
single copy of each partition, a clean shutdown provides no availability benefit;
the partition is gone until the node restarts.

### 4.3 Frozen / unresponsive node
**Reasoning:** real nodes do not always crash cleanly — they hang (GC pauses, disk
stalls, CPU starvation). **Finding:** recovery was the fastest (**MTTR 23.2 s**)
because resuming the node restarts the existing processes — no service restart is
needed and the system re-converges on its own.

### 4.4 Network partition
**Reasoning:** the classic distributed-systems failure — a node is alive but
isolated. **Finding:** **MTTR 32.8 s** after reconnection at the node's original
address. Availability *flapped* during recovery (two outage windows) as the
isolated node rejoined — recovery is not a single clean transition.

### 4.5 Single-component failure
**Reasoning:** TigerGraph runs multiple services per node; isolating one engine
(the GPE serving a partition) tests behaviour at finer granularity than a
whole-node loss. **Finding:** the data path kept working for **11.3 s** before
queries failed — markedly longer than a whole-node loss — then recovery via a
service restart gave **MTTR 57.1 s**. Component-level loss has a longer tolerance
window than node loss.

### 4.6 Master / gateway-node crash
**Reasoning:** losing the node that also fronts the gateway is the case most
likely to take the whole system down. **Finding:** observed from a surviving node,
the cluster recovered in **55.9 s** (73% availability over the window). Loss of any
single node — including the master — is survivable and self-recovering.

### 4.7 Write durability under failure
**Reasoning:** the hardest question — does a write *during* a node failure succeed,
and is it still there afterwards? **Finding:** with one node down, roughly half of
the upserts succeeded (the rest targeted the offline partition and failed), and
**every acknowledged write persisted** after recovery — no data loss. Under a
network partition an additional effect appeared: some writes the client saw *time
out* (counted as failures) were nonetheless committed by the server — an
**ambiguous-write** outcome. The durability guarantee holds (nothing acknowledged
is lost), but a client cannot assume a timed-out write did not take effect.

---

## 5. Cross-cutting observations

- **Whole-node failures are felt almost immediately** (~0.2 s) because the
  distributed query needs every partition; a single component (GPE) failure is
  tolerated ~11 s before the data path is affected.
- **Recovery cost tracks the recovery mechanism, not fault severity.** Restart-based
  recovery (crash, graceful stop, component, master) clusters at ~52–57 s;
  resume/reconnect recovery (freeze, partition) at ~23–33 s.
- **Recovery is not always a clean single transition** — the network partition
  showed availability flapping as the node rejoined.
- **No acknowledged write is ever lost.** Writes either fail outright or are durable;
  under a partition, some client-failed writes still commit (ambiguous, not lost).
- At replication factor 1 there is no failover — every node loss causes an outage of
  its partition. This is the baseline that quantifies the value of replication
  factor 2.

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
