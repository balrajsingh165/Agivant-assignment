"""Test harness for TigerGraph high-availability node-failure testing.

Modules:
    cluster   access to the cluster (docker, gadmin, gateway, HA detection)
    faults    node fault injection and recovery
    probe     in-process availability sampling and MTTR analysis
    scenario  end-to-end read- and write-path failure scenarios
"""
