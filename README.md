# RTLAMR — Itron ERT Smart Meter Reader

Read 900 MHz Itron ERT smart meters using an RTL-SDR dongle, then push consumption data into Home Assistant (Energy Dashboard), MQTT, or a local SQLite database.

## Quick Install

This is a [Hermes Agent](https://hermes-agent.nousresearch.com) skill. To install:

```bash
mkdir -p ~/.hermes/skills/hardware
git clone https://github.com/<YOUR_ORG>/rtlamr-meter-reader ~/.hermes/skills/hardware/rtlamr-meter-reader
```

Then reload skills (`/reload` in chat, or restart the gateway) and it becomes available as `/rtlamr-meter-reader`.

**Not using Hermes?** The [SKILL.md](./SKILL.md) is a standalone guide — follow it start to finish for a manual setup. The scripts in [`scripts/`](./scripts/) work independently of Hermes.

## Contents

| File | Purpose |
|------|---------|
| [`SKILL.md`](./SKILL.md) | Full setup guide — 14 steps, troubleshooting, verification checklist |
| [`scripts/rtlamr-ha-bridge.sh`](./scripts/rtlamr-ha-bridge.sh) | Production bridge: reads meter, pushes to HA REST API |
| [`scripts/rtlamr-mqtt-bridge.py`](./scripts/rtlamr-mqtt-bridge.py) | MQTT bridge: publishes to HA auto-discovery topics |
| [`references/`](./references/) | Reference docs on bridge validation, data verification, HA API |
| [`LICENSE`](./LICENSE) | MIT |

## Requirements

- Linux machine with USB port (or Proxmox host with RTL-SDR)
- RTL2838 DVB-T dongle (0bda:2838)
- Home Assistant instance (or Mosquitto broker, or just a text file — pick your delivery)
- 900 MHz Itron ERT meter in range

## Pipeline

```
RTL-SDR dongle → rtl_tcp → rtlamr → bridge script → Home Assistant / MQTT / SQLite
```

## License

MIT
