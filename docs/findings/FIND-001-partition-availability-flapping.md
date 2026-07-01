# FIND-001 — Availability flaps during recovery from a network partition

| | |
|---|---|
| **Related test** | TC-NF-004 (network partition, isolate `tg3`) |
| **Severity** | Low–Medium |
| **Type** | Recovery behaviour |

## Summary

When a partitioned node is reconnected, availability does **not** recover in a
single clean transition. The probe recorded **two separate outage windows** — the
data path recovered, briefly dropped again, and then stabilised — as the node
rejoined the cluster.

## Steps to reproduce

1. Load the sample graph; confirm the query endpoint returns HTTP 200.
2. Isolate `tg3` from the cluster network (`docker network disconnect tgnet tg3`).
3. Probe the `ping_count` query every 250 ms from a surviving node.
4. Reconnect `tg3` at its original IP and keep probing.

## Expected vs actual

- **Expected:** one outage window — down at disconnect, up once reconnected.
- **Actual:** two outage windows; a short second dip occurred *after* the first
  apparent recovery, before availability held steady.

## Impact

A client that treats the first successful response after a partition as "fully
recovered" may hit a second brief failure. Recovery is not atomic.

## Recommendation

Define recovery as **sustained** availability (a run of consecutive successes),
not the first success. The MTTR metric in this suite already measures the end of
the *last* outage window for this reason.
