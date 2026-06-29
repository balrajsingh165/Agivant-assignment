# Setup

## Requirements

- Docker (with ~16 GB of memory available to run the 3-node cluster and suite).
- [`uv`](https://docs.astral.sh/uv/) for the Python test environment.

## 1. License key

High availability is a licensed capability, so the **Enterprise** edition is
required (the Community edition is single-server only).

- Enterprise license: https://info.tigergraph.com/enterprise-free
  (register with a business email; the key is delivered by email).
- Save it as `license.txt` in the repo root (excluded from version control).

The installer reads the license and selects the replication factor automatically:
replication factor 2 (HA) when the license enables Data HA, otherwise 1 (non-HA).

## 2. Install package

- Download portal: https://dl.tigergraph.com/ (Linux x86_64 offline tarball).
- The portal serves the latest 4.1.x patch (e.g. `tigergraph-4.1.4-offline.tar.gz`).
- Place it in `./pkg/` (gitignored), or point `TG_TARBALL` at its path.

## 3. Build and test

```bash
docker compose up -d
bash scripts/01-install.sh
bash scripts/load-sample-graph.sh
uv sync
uv run pytest
```

## Topology

- 3 Docker containers `tg1` / `tg2` / `tg3` on bridge network `tgnet`, static IPs.
- HA: **1 partition × replication factor 2** (smallest valid HA cluster).
- Non-HA: **3 partitions × 1 replica** (used when the license has no HA entitlement).
- Each node's GraphStudio/REST gateway is published to the host (14240/14241/14242).
