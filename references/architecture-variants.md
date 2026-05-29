# Architecture Variants

## Proxmox Multi-Host (dongle on PVE host, software on VM/LXC)

```
PVE Host (.100)               VM/LXC (.200)
┌──────────────┐  :1234   ┌────────────────────────┐
│ RTL-SDR dongle │───►rtl_tcp──► rtlamr → HA push   │
│ (0bda:2838)    │  network    │ → systemd timer     │
└──────────────┘           └────────────────────────┘
```

- `rtl_tcp` must bind to `0.0.0.0` (not `127.0.0.1`)
- DVB driver blacklisting happens on the PVE host (where the dongle lives)
- `rtlamr` connects to the PVE host's LAN IP
- No USB passthrough needed — `rtl_tcp` runs natively on PVE, more reliable than LXC passthrough

See the main [SKILL.md](../SKILL.md) for the single-host (simplest) setup.
