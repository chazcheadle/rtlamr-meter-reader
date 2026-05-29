---
name: rtlamr-meter-reader
description: Use when setting up RTL-SDR-based smart meter reading with rtlamr, connecting it to Home Assistant via MQTT or REST API, or troubleshooting 900MHz ERT meter capture.
version: 2.2.0
author: Hermes Agent
license: MIT
trigger: User asks about reading a power meter with RTL-SDR, rtlamr, rtlamr-collector, smart meter SDR, or Itron ERT data in Home Assistant
metadata:
  hermes:
    tags: [sdr, rtl-sdr, smart-meter, itron, 900mhz, home-assistant]
    related_skills: []
---

# RTLAMR — Itron ERT Smart Meter Reader

Read 900 MHz Itron ERT smart meters using an RTL-SDR dongle, then push consumption data into Home Assistant (Energy Dashboard), MQTT, or a local SQLite database.

## Overview

The pipeline is:

```
RTL-SDR dongle → rtl_tcp → rtlamr → bridge script → Home Assistant / MQTT / SQLite
```

The dongle captures 900 MHz ERT broadcasts from your utility meter. `rtlamr` decodes them. A bridge script parses the JSON output and pushes it to your chosen destination.

**What you get:** A `total_increasing` sensor in HA that feeds the Energy Dashboard. The dashboard computes rate (kW) and daily consumption automatically from the cumulative register value.

## When to Use

- You have a 900 MHz Itron smart meter (ERT protocol) in range
- You have an RTL-SDR dongle (RTL2838, 0bda:2838) and a Linux machine
- You want to track household power consumption in Home Assistant
- You need to diagnose why rtlamr produces no decodes despite a working dongle

## Step-by-Step Procedure

Set aside about 30 minutes. You need a Linux machine with the RTL-SDR plugged in and Home Assistant running on your network.

### 1. Check the dongle is recognized

```bash
lsusb | grep -i rtl
```

Expected output: `Realtek Semiconductor Corp. RTL2838 DVB-T`

If nothing shows, unplug and re-plug the dongle. If the kernel DVB driver has claimed the device (common on Linux), the fix is in **Step 2**.

### 2. Unload the kernel DVB driver (one-time)

The kernel's `dvb_usb_rtl28xxu` driver claims RTL-SDR dongles on hotplug, blocking userspace tools.

```bash
sudo rmmod dvb_usb_rtl28xxu 2>/dev/null
```

If this fails with "Module is in use", unbind it from sysfs:

```bash
# Find the device path
ls /sys/bus/usb/devices/*/driver | xargs readlink 2>/dev/null | grep dvb
# Unbind it (adjust the path from the output above)
echo '1-13:1.0' | sudo tee /sys/bus/usb/drivers/dvb_usb_rtl28xxu/unbind
sudo modprobe -r dvb_usb_rtl28xxu dvb_usb_v2 rtl2832 rtl2832_sdr
```

### 3. Blacklist the DVB driver (survives reboot)

The blacklist alone isn't enough — a second line catches explicit module load requests:

```bash
sudo bash -c 'echo "blacklist dvb_usb_rtl28xxu
install dvb_usb_rtl28xxu /bin/true" > /etc/modprobe.d/dab-rtl-sdr.conf'
sudo update-initramfs -u
```

Both lines are required. Without `update-initramfs -u`, the blacklist won't apply during early boot.

### 4. Install udev permissions (needed for non-root SDR access)

Without this, `rtl_tcp` run as a regular user (or via systemd user service) will get `usb_open error -3` — permission denied.

```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/60-rtl-sdr-permissions.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

This gives read/write access to the dongle for all users. Without it, only root can access the device.

### 5. Install rtl-sdr tools

```bash
# Build dependencies
sudo apt-get install -y libusb-1.0-0-dev cmake build-essential git pkg-config

# Build rtl-sdr from source
git clone https://git.osmocom.org/rtl-sdr.git /tmp/rtl-sdr
cd /tmp/rtl-sdr && mkdir build && cd build
cmake .. -DDETACH_KERNEL_DRIVER=ON -DINSTALL_UDEV_RULES=ON
make -j$(nproc) && sudo make install && sudo ldconfig
```

`pkg-config` is required — without it, CMake can't find libusb headers.

### 6. Install rtlamr decoder

```bash
curl -L https://github.com/bemasher/rtlamr/releases/download/v0.9.5/rtlamr_linux_amd64.tar.gz -o /tmp/rtlamr.tar.gz
tar xzf /tmp/rtlamr.tar.gz -C /tmp/
cp /tmp/rtlamr ~/.local/bin/rtlamr && chmod +x ~/.local/bin/rtlamr
```

### 7. Start the SDR server

If the dongle is plugged into this machine:

```bash
rtl_tcp -a 127.0.0.1 -p 1234 &
```

If the dongle is on a different machine (e.g. a Proxmox host — see `references/architecture-variants.md`), use `-a 0.0.0.0` and connect via its LAN IP.

### 8. Discover your meter ID

Run a 60-second scan to see which ERT meters are in range:

```bash
rtlamr -server=localhost:1234 -msgtype=scm,idm -duration=60s -format=json > /tmp/meters.json
python3 -c "
import json
meters = set()
with open('/tmp/meters.json') as f:
    for line in f:
        if not line.strip() or line.startswith('C:'): continue
        try:
            msg = json.loads(line)
            m = msg.get('Message', {})
            mid = m.get('ID', m.get('ERTSerialNumber'))
            if mid: print(mid)
        except: pass
" | sort -u
```

Your meter will appear as an 8-digit number (e.g. `12345678`). It's the one that appears most often and shows monotonically increasing consumption. **Save this number — it's your `METER_ID`.**

### 9. Get your Home Assistant access token

In HA: **Settings → System → Long-Lived Access Tokens → Create Token**. Copy the token string (starts with `eyJ`).

### 10. Create the project directory and configuration

```bash
mkdir -p ~/projects/rtlamr-ha-bridge ~/.config/

cat > ~/.config/rtlamr-ha-bridge.env << EOF
HASS_URL=http://homeassistant:8123
HASS_TOKEN=eyJ...your-token-here...
METER_ID=12345678
EOF
# Adjust HASS_URL to your HA instance (try http://homeassistant:8123,
# http://ha:8123, or your HA machine's IP:8123)
```

### 11. Get the bridge script and do a dry-run test

```bash
# Copy the bridge script from this repo's scripts/ directory:
cp scripts/rtlamr-ha-bridge.sh ~/projects/rtlamr-ha-bridge/
chmod +x ~/projects/rtlamr-ha-bridge/rtlamr-ha-bridge.sh

# Dry run — reads the meter and prints the value without pushing to HA
cd ~/projects/rtlamr-ha-bridge
source ~/.config/rtlamr-ha-bridge.env && ./rtlamr-ha-bridge.sh --dry-run
```

Expected output: `Meter 12345678: 6739308 Wh (6739.3 kWh)`

### 12. Install the systemd timer (auto-runs every 5 minutes)

See `references/systemd-setup.md` for the service unit, timer unit, and enable-linger setup.

### 13. Verify it's working

After 5 minutes, check the journal:

```bash
journalctl --user -u rtlamr-ha-bridge.service -n 10
```

Expected output: `HA 200: state=6739308`

### 14. Add to the Energy Dashboard

In HA: **Settings → Energy → Add consumption → select `sensor.rtlamr_power_meter`**. Choose "kWh" as the unit.

The first push seeds the sensor with your real cumulative register value. HA tracks only the *changes* from there.

## Configuration Reference

All scripts are configured via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `METER_ID` | **Yes** | — | Your meter's 8-digit ID from the discovery scan |
| `HASS_TOKEN` | **Yes** | — | HA long-lived access token |
| `HASS_URL` | No | `http://homeassistant:8123` | Home Assistant base URL |
| `RTLTCP_SERVER` | No | `localhost:1234` | rtl_tcp server (`host:port`) |
| `RTLAMR_GAIN` | No | `10` | R820T gain index for 912 MHz |
| `SENSOR_ID` | No | `sensor.rtlamr_power_meter` | HA sensor entity name |
| `SCAN_DURATION` | No | `50` | Capture window in seconds |

## Architecture Options

### Single-host (simplest)

All components on one machine — `rtl_tcp`, `rtlamr`, and the bridge script. Everything talks over `127.0.0.1`.

### Proxmox multi-host

See `references/architecture-variants.md` for the dongle-on-PVE-host setup.

### 3D-printed enclosure

RTL-SDR dongles are bare boards and the MCX antenna connector is fragile. A printed case protects both. See `enclosure/` for printable 3D model files.

## Delivery Options

After the bridge captures a reading, you have three choices for where it goes:

| Option | Best for |
|--------|----------|
| **HA REST API** | Simplest path. Zero extra services. Just a token. |
| **MQTT auto-discovery** | Already running Mosquitto. Want real-time. Multiple consumers. See `references/mqtt-setup.md`. |
| **Local SQLite** | DIY analytics. Grafana via sqlite_exporter. Not using HA. See `references/sqlite-backend.md`. |

You can run all three simultaneously — the overhead is negligible.

### HA REST API (default)

The bridge script pushes directly to the HA API using `urllib` (stdlib). No extra dependencies.

```bash
# The rtlamr-ha-bridge.sh script handles this automatically.
# No additional setup beyond the env file.
```

## Common Pitfalls

### HASS_URL without a scheme

If `HASS_URL` is set to `homeassistant:8123` (no `http://`), Python's `urllib` treats it as a relative path and fails silently. The bridge script auto-prepends `http://` if the scheme is missing, but if you set it in a systemd `EnvironmentFile`, double-check:

```bash
# CORRECT
HASS_URL=http://homeassistant:8123

# SILENTLY WRONG
HASS_URL=homeassistant:8123
```

### Scan windows can land between transmissions

Meters broadcast roughly every 30–60 seconds. A 50-second window usually catches one. Sometimes it doesn't. The script retries once after 15 seconds, then exits cleanly (exit 0) for the next timer tick. An empty cycle is normal — don't treat it as a failure.

### Gain index must be set explicitly

`rtlamr` defaults to `-gainbyindex=0` (near-zero gain), which decodes nothing at 912 MHz. Use **gain index 10**:

```bash
rtlamr -server=... -gainbyindex=10 -agcmode=true -msgtype=scm,idm ...
```

Override via the `RTLAMR_GAIN` environment variable.

### Entity seeding must use the real register value

For `total_increasing` sensors, HA computes consumption as `current - previous`. If you create a sensor with `state: 0` and push your 6.7 MWh cumulative reading on the next tick, HA registers a **6.7 MWh spike** as today's consumption.

**The first push must be the actual cumulative meter value.** The bridge does this automatically — it reads the meter and pushes whatever it returns. Don't seed at 0.

### Neighbor meters cause consumption spikes

The RTL-SDR decodes every ERT meter in range. If a neighbor's packet arrives last in the scan window, the bridge accepts their consumption as yours. **Always verify the meter ID filter in the bridge script.** See `references/bridge-validation.md` for the full analysis of a real 3.6 MWh spike incident and the validation rules that prevent recurrence.

### last_reset: Required for REST-API sensors, omit for MQTT

REST-API sensors (no `unique_id`) require `last_reset` set to midnight UTC for Energy Dashboard daily totals to compute correctly. MQTT auto-discovery sensors handle this internally and must NOT have `last_reset`. See `references/rest-api-sensor-lifecycle.md` for the full treatment and the detection signal (dashboard total < known always-on load).

### rtl_tcp gets stuck in `deactivating`

After `systemctl stop`, if the dongle was busy, the service can enter a permanent `deactivating (stop-sigterm)` state. Fix via SSH to the host:

```bash
pkill -9 rtl_tcp
systemctl reset-failed rtl_tcp && systemctl restart rtl_tcp
```

## References

- `references/bridge-validation.md` — Validation rules for meter ID filtering and spike detection
- `references/calibration-crosscheck.md` — Cross-referencing RTLAMR readings against known loads
- `references/rest-api-sensor-lifecycle.md` — REST API sensor lifecycle, including `last_reset` requirements
- `references/architecture-variants.md` — Proxmox multi-host setup
- `references/mqtt-setup.md` — MQTT broker and auto-discovery configuration
- `references/sqlite-backend.md` — SQLite schema and queries
- `references/systemd-setup.md` — Systemd timer service and timer units
- `enclosure/` — Printable 3D model files for the RTL-SDR case
