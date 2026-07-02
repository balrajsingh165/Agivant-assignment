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

## High availability

The cluster runs at **replication factor 2** (1 partition, 2 replicas on separate
nodes). The installer selects the replication factor from the license: RF=2 when
the license enables Data HA, otherwise RF=1. The suite **auto-detects** the mode
(`cluster.ha_mode`) and applies HA expectations only when HA is licensed, so the
same tests characterise either configuration.

Result (see `docs/REPORT.md`): under HA, freeze / partition / component failures run
at **100% availability with zero downtime** (a replica serves), while losing a live
node costs a short failover window (~24 s) — versus ~52 s outages at RF=1.

## Layout

```
docker-compose.yml, Dockerfile   3-node cluster (static IPs, auto-restart)
pyproject.toml                   project + pytest config (managed with uv)
scripts/
  01-install.sh                  installer; replication factor from the license
  load-sample-graph.sh           schema + data + distributed query endpoints
  sample-graph/*.gsql            schema, loading job, queries
  lib.sh                         shared shell helpers for the setup scripts
  build_report.py                render docs/report.html from results/
  build_deliverables.py          render TestPlan.xlsx/.pdf + TraceabilityMatrix.xlsx + bug docx
tigergraph_ha/                   test harness package
  cluster.py                     docker / gadmin access + HA detection + gsql/service state
  faults.py                      fault injection and recovery
  probe.py                       availability probe + MTTR analysis
  scenario.py                    read- and write-path failure scenarios
tests/                           pytest suite (18 cases; ids TC-QL/SV/LJ/NF/WR/NG/BD/CFG-*)
  test_gsql_queries.py           GSQL query combinations (functional)
  test_service_health.py         service status + crash behaviour
  test_loading_job.py            loading job from a CSV source
  test_node_failures.py          6 node-failure modes: availability + MTTR
  test_write_durability.py       write availability + durability under failure
  test_negative_boundary.py      invalid query; two-node boundary
  test_config_change.py          gadmin config change + restart-all resilience
results/                         per-scenario JSON (ha_* HA, noha_* RF=1 baseline)
logs/                            per-test logs
docs/
  REPORT.md                      test report (HA results, comparison, findings, MTTR)
  TestPlan.md / .xlsx / .pdf     test cases (email format: ID, precondition, steps, API)
  TraceabilityMatrix.xlsx        manual test case -> automation mapping
  report.html                    pytest HTML execution report
  TestExecutionReport.xlsx       per-case results (status, MTTR, availability)
  screenshots/                   command evidence screenshots (SS-01..SS-12)
  findings/                      bug reports with root-cause analysis (BUG-*.md and .docx)
  SETUP.md, install_conf.template.json
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

**Reports:**
- HTML execution report: `uv run pytest --html=docs/report.html --self-contained-html` (committed at `docs/report.html`)
- Allure (optional): `uv run pytest --alluredir=allure-results` then `allure serve allure-results`
- Per-test logs land in `logs/`.

**Office deliverables** (test plan xlsx+pdf, traceability matrix, bug reports):
`uv run --with openpyxl --with python-docx --with reportlab python scripts/build_deliverables.py`

**Screenshots** of the executed commands are in `docs/screenshots/`.

## Measurement

`tigergraph_ha/probe.py` issues the `ping_count` query every 250 ms from an
observer node (any node other than the fault target, so even the gateway node can
be failed) and records every result. From the log it derives availability,
outage windows, MTTD and MTTR relative to the fault-injection time.
`scenario.write_scenario` additionally measures write availability and data
durability across a failure.
