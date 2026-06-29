# TigerGraph High-Availability Node-Failure Testing

Install TigerGraph with high availability (HA) and test its product behaviour and
recovery under node failures, reporting measured MTTR.

> **Version:** the assignment specifies 4.1.3; TigerGraph's portal serves only the
> latest patch of the line (4.1.4). 4.1.4 (same 4.1 minor line) is used.

## Architecture

A 3-node TigerGraph cluster runs as three Docker containers (`tg1`, `tg2`, `tg3`)
on a bridge network `tgnet` with static IPs. Each node's gateway is published to
the host (`14240`/`14241`/`14242`). Containers make node-failure injection clean
and repeatable: `docker kill` (crash), `docker stop` (graceful), `docker pause`
(freeze), `docker network disconnect` (partition).

```
tg1 172.20.0.11  ->  host 14240
tg2 172.20.0.12  ->  host 14241        topology: 1 partition x 2 replicas (HA)
tg3 172.20.0.13  ->  host 14242                   or 3 x 1 (non-HA)
```

## HA is optional and auto-detected

HA depends on the license's replication entitlement. The suite **detects the
active configuration** and runs the matching track with no manual switches:

- **License enables HA** → cluster installs at replication factor 2 and the suite
  runs the HA track (a node loss should keep the data path available; MTTR in
  seconds).
- **Otherwise** → cluster installs at replication factor 1 and the suite runs the
  non-HA baseline (a node loss takes its partition offline until restored). The
  HA-only assertions are skipped.

Provide an HA-capable license and the HA tests run automatically; without one they
are skipped and the baseline runs. See `docs/REPORT.md`.

## Layout

```
docker-compose.yml, Dockerfile   3-node cluster (static IPs, auto-restart)
pyproject.toml                   project + pytest config (managed with uv)
scripts/
  01-install.sh                  installer; replication factor from the license
  load-sample-graph.sh           schema + data + distributed query endpoints
  sample-graph/*.gsql            schema, loading job, queries
  lib.sh                         shared shell helpers for the setup scripts
tigergraph_ha/                   test harness package
  cluster.py                     docker / gadmin access + HA detection
  faults.py                      fault injection and recovery
  probe.py                       availability probe + MTTR analysis
  scenario.py                    read- and write-path failure scenarios
tests/                           pytest suite
  test_node_failures.py          read availability + MTTR per failure mode
  test_write_durability.py       write availability + data durability
results/                         per-scenario result JSON
docs/                            REPORT.md, SETUP.md, install template
```

## Quick start

```bash
docker compose up -d                 # 1. start the 3 nodes
bash scripts/01-install.sh           # 2. install (replication factor auto-selected)
bash scripts/load-sample-graph.sh    # 3. load sample graph + query endpoints
uv sync                              # 4. create the test environment
uv run pytest                        # 5. run the failure suite -> results/
```

Prerequisites (license + install package) are in `docs/SETUP.md`. Running the
3-node cluster plus the suite needs roughly 16 GB of free memory.

## Measurement

`tigergraph_ha/probe.py` issues the `ping_count` query every 250 ms from an
observer node (any node other than the fault target, so even the gateway node can
be failed) and records every result. From the log it derives availability,
outage windows, MTTD and MTTR relative to the fault-injection time.
`scenario.write_scenario` additionally measures write availability and data
durability across a failure.
