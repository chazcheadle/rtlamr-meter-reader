# RTLAMR Calibration Cross-Check

Detect under-reporting or stale sensor data by cross-referencing RTLAMR readings against a known load (UPS, Kill-A-Watt, or any calibrated device).

## Why Calibrate

RTLAMR can under-report for several reasons that look identical in the Energy Dashboard — low consumption, all bars, everything looks fine, but the numbers don't add up against actual loads:

- **Wrong Kh factor** — the meter's pulse weight (watts per pulse) is misconfigured in the bridge, so every reading is off by a constant multiplier
- **Dropped pulses** — weak SDR signal causes the dongle to miss transmissions, cumulative value drifts low over time
- **Stale sensor** — the HA entity the Energy Dashboard uses stopped updating (last_updated is hours/days old) but still displays as a valid reading; dashboard sees a flat line
- **Phase issue** — on split-phase 240V service (US residential), the SDR may only reliably capture one leg's meter pulses, reading ~50% of real consumption

## Cross-Check Procedure

### 1. Establish a Known Load

Find something you can turn on whose power draw you know precisely:

- **UPS display** — CyberPower/APC LCD showing real power in **watts**, not VA (critical distinction; many UPS LCDs show VA by default)
- **Kill-A-Watt / plug-in meter** on a known device
- **Device with known TDP** — RTX 3090 at idle: 7-8W (from nvidia-smi), at load: 350W
- **Grow light** — LED panel with a published spec (e.g. 200W, 600W)
- **Space heater** — resistive heaters publish their draw (1,500W for a typical unit)

### 2. Read Both Meters Simultaneously

```bash
# Get the live RTLAMR value (whichever sensor is most recent):
source ~/.hermes/config/homeassistant.env
curl -s -H "Authorization: Bearer $HASS_TOKEN" \
  "http://${HASS_URL}/api/states/sensor.rtlamr_power_meter_v3" | \
  python3 -m json.tool

# Note: state, last_updated, and last_reset
```

From the response, check:
- **state** — the cumulative Wh reading
- **last_updated** — if it's more than ~15 minutes old, the data feed is stale
- **last_reset** — should be absent or at most daily; if set on every push, readings are corrupted (see `bridge-validation.md`)

### 3. Compute Instantaneous Power from Cumulative Readings

```python
# Two readings minutes apart = compute avg watts
# Wh_delta = reading2 - reading1
# hours = (t2 - t1) in decimal hours
# avg_watts = Wh_delta / hours

# Example: 166W UPS load should add ~166 Wh per hour to the cumulative
# If RTLAMR shows ~83 Wh added in that same hour = 2x under-report
```

### 4. Interpret the Gap

| UPS says | RTLAMR shows in that hour | Likely issue |
|---|---|---|
| 166W | ~166 Wh added (1:1) | Calibrated correctly |
| 166W | ~80-90 Wh added (~2:1) | **Half-pulse** — likely phase issue or wrong Kh divisor (meter is 240V, SDR only captures one leg) |
| 166W | ~0-20 Wh added (10:1+) | **Stale sensor** — check last_updated; or **Kh factor off by factor of 10** |
| 166W | Wildly varying | **Neighbor interference** — packets from nearby meters corrupting the reading; check meter ID filter |

### 5. Check All Three Sensors

If you have multiple RTLAMR sensors (v1, v2, v3) reading the same meter ID:

```bash
for sensor in sensor.rtlamr_power_meter sensor.rtlamr_power_meter_v2 sensor.rtlamr_power_meter_v3; do
  echo "=== $sensor ==="
  curl -s -H "Authorization: Bearer $HASS_TOKEN" \
    "http://${HASS_URL}/api/states/${sensor}" | \
    python3 -c "
import sys,json
d = json.load(sys.stdin)
print('state:', d['state'])
print('last_updated:', d['attributes'].get('last_updated','N/A'))
print('last_reset:', d['attributes'].get('last_reset','N/A'))
"
done
```

Signs of trouble:
- **Different states** — sensors at different cumulative values mean they were created/reset at different times; the Energy Dashboard is likely reading the stale lowest one
- **last_updated more than ~1 hour ago** — that sensor's feed is dead; dashboard may still reference it
- **Sensors show same state, same last_updated** — one sensor is an alias, not independent; check if they share the same `meter_id`

## Energy Dashboard Sensor Selection

In HA Energy Dashboard configuration (Settings → Energy → Add consumption), you select which sensor entity feeds the graph. If you select a **stale** sensor, the graph shows flat or artificially low consumption because the sensor stopped updating. This is the most common cause of "my Energy Dashboard says 2 kWh but my UPS says the server alone uses 4 kWh."

**Fix:** Delete the stale sensor from the Energy Dashboard and add the live one instead. HA does not automatically migrate — you must manually reconfigure.

## Real-World Example (28 May 2026)

- **UPS reading:** 171 VA / 166 W (Dell T7280 server + cable modem + WiFi6 router + phone + PoE camera)
- **RTLAMR v1:** 6,731,448 Wh — last_updated May 27 04:49 (stale, 40h)
- **RTLAMR v2:** 6,731,510 Wh — last_updated May 27 05:09 (stale, 40h)
- **RTLAMR v3:** 6,739,733 Wh — last_updated May 28 21:08 (live)
- **HA Energy Dashboard reading:** 1.98 kWh for the day
- **Expected from UPS alone (166W × 17h):** ~2.8 kWh
- **V3 cumulative delta (40h):** ~8.2 kWh → ~205W average (more realistic given fridge/freezer cycling + UPS load)

**Conclusion:** The Energy Dashboard was referencing a stale sensor. After reconfiguring to use v3, the daily total would more accurately reflect actual consumption.
