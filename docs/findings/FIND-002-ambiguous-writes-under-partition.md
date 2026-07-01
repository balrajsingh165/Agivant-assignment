# FIND-002 — Ambiguous write outcomes during a network partition

| | |
|---|---|
| **Related test** | TC-WR-002 (writes during a network partition, isolate `tg2`) |
| **Severity** | Medium |
| **Type** | Write consistency / client contract |

## Summary

During a network partition, some vertex upserts that the **client saw time out**
(and therefore counted as failures) were **nonetheless committed** by the server.
After recovery, the vertex count increased by more than the number of writes the
client had acknowledged as successful.

No acknowledged write was ever lost — the durability guarantee holds — but the
*client's* success/failure signal is unreliable under a partition.

## Steps to reproduce

1. Record the baseline vertex count from a surviving node.
2. Isolate `tg2` from the cluster network.
3. Upsert a batch of new vertices through a surviving node during the outage; count
   client-side successes and failures.
4. Reconnect `tg2`, wait for recovery, and re-read the vertex count.

## Expected vs actual

- **Expected:** a write the client sees time out did not take effect; the count
  rises by exactly the number of acknowledged successes.
- **Actual:** the count rose by **more** than the acknowledged successes — some
  timed-out writes had committed.

## Impact

A client cannot assume a timed-out write did not happen. Naive retry of a
"failed" write could double-apply it.

## Recommendation

Use **idempotent writes** (upsert by a stable primary key, as this suite does) so
a retry is safe, and reconcile state after a partition rather than trusting the
client-side outcome alone.
