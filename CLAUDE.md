# CLAUDE.md — Project Guidelines

## What this project is
Practical QA assessment for **Agivant**: install **TigerGraph 4.1.3 with High Availability (HA)**,
test product behavior under **node failures**, and write a test report with measured recovery times.

Deliverables expected by the reviewer:
1. A working HA TigerGraph cluster.
2. `REPORT.md` — test cases, *reasoning* for each, findings (what works / what doesn't),
   downtime + **MTTR** with how it was measured.
3. This GitHub repo with the scripts/automation used.

Evaluation criteria from the brief: technical accuracy of failover logic, problem-solving on
edge cases where recovery/resume fails, and clear documentation.

## Environment
- Host: Windows 11 + WSL2 + Docker Desktop (Docker 29.2, ~20.8 GB available).
- Cluster: **3 Docker containers** `tg1`/`tg2`/`tg3` on bridge net `tgnet`, 5 GB each.
- `tg1` publishes GraphStudio/REST on host port `14240`.
- Version: portal serves 4.1.4 (4.1.3 not separately available); 4.1.4 used.
- HA is **license-gated**: the Enterprise Free license has `DataHA: Enable:false`,
  so it permits RF=1 only. The harness auto-detects this (`cluster.ha_mode`):
  - HA license -> RF=2 (1 partition x 2 replicas), full failover suite.
  - no HA license -> RF=1 (3 partitions x 1 replica), non-HA baseline suite.

## Repo layout
- `Dockerfile`, `docker-compose.yml` — node image + 3-node cluster (static IPs).
- `scripts/` — bash setup: `01-install.sh`, `load-sample-graph.sh`, `lib.sh`, `sample-graph/`.
- `tigergraph_ha/` — Python test harness: `cluster.py`, `faults.py`, `probe.py`, `scenario.py`.
- `tests/` — pytest suite (node failures, write durability).
- `pyproject.toml` — project + pytest config; deps managed with **uv** (`uv sync`, `uv run pytest`).
- `pkg/` — install tarball (gitignored). `results/` — per-scenario `.json` (committed).
- `docs/` — `REPORT.md` (deliverable), `SETUP.md`, `install_conf.template.json`.

## Working rules (from the user)
- **Never commit or push automatically.** Provide a ready-to-use commit message.
- Commit message ends with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- **Code: docstrings yes, inline comments minimal.**
- Secrets (license key, `.env`) never committed; gitignored.
- **Docs must read as a clean engineer's submission** — no AI/meta talk, no mention
  of the hiring process or any back-channel. Frame HA as an auto-detected option.

## Test harness (Python/pytest, run via uv)
The harness is Python (not bash) — Windows-robust process spawning, no fork/path issues.
`probe.Probe` samples the `ping_count` query every 250 ms from an observer node;
`probe.analyze` derives MTTD, downtime, MTTR, availability. `scenario.read_scenario`
and `scenario.write_scenario` inject a fault, recover, and save `results/<name>.json`.
Faults: kill / stop / pause / partition / component(GPE) / recover.
HA is auto-detected (`cluster.ha_mode`); tests assert HA expectations only when licensed.
