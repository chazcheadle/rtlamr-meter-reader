# REST-API Sensor Lifecycle

Created via `POST /api/states/{entity_id}`. Key difference from MQTT auto-discovery: these sensors have **no `unique_id`** and cannot be managed from the HA UI.

## Characteristics

- `unique_id` is absent → UI shows: *"This entity does not have a unique ID, therefore its settings cannot be managed from the UI."*
- No platform/integration listed in entity registry
- `context.user_id` is set to the token owner's user ID (not an integration)
- `last_reset` is required for Energy Dashboard daily tracking (MQTT sensors with `unique_id` handle this internally)

## Lifecycle

### Creation

```bash
curl -X POST -H "Authorization: Bearer $HASS_TOKEN" \
  -H "Content-Type: application/json" \
  "http://homeassistant:8123/api/states/sensor.rtlamr_power_meter_v3" \
  -d '{"state": "6740000", "attributes": {"unit_of_measurement": "Wh", "device_class": "energy", "state_class": "total_increasing", "friendly_name": "Power Meter"}}'
```

### Marking unavailable (workaround for "cannot delete from UI")

REST-API sensors cannot be deleted or disabled via the HA UI. To remove them from dashboards and the Energy Dashboard:

```bash
curl -X POST -H "Authorization: Bearer $HASS_TOKEN" \
  -H "Content-Type: application/json" \
  "http://homeassistant:8123/api/states/sensor.rtlamr_power_meter" \
  -d '{"state": "unavailable", "attributes": {}}'
```

This sets the sensor to `unavailable`. The empty attributes object clears all previous metadata. HA's database still has historical data but the sensor will not appear in dashboards.

### Permanent removal (not possible via REST)

Only possible by:
1. Stopping the script/service that creates the entity
2. Accessing HA's `.storage/core.entity_registry` directly (requires HAOS disk mount or internal access)
3. Using the HA WebSocket API (not exposed via REST)

### Migration: REST → MQTT

If you want the advantages of MQTT auto-discovery (unique_id, UI management, no `last_reset` needed):

1. Set up Mosquitto in HA
2. Configure the MQTT integration in HA (Settings → Devices & Services → MQTT)
3. Publish discovery config to `homeassistant/sensor/rtlamr_{meter_id}/config` (retained)
4. Publish state to `homeassistant/sensor/rtlamr_{meter_id}/state`
5. Mark the old REST sensor as unavailable (see above)
6. Add the new MQTT sensor to Energy Dashboard

## last_reset: Why It Matters and How to Diagnose

### The Core Rule

| Integration type | `last_reset` | Why |
|-----------------|-------------|-----|
| **MQTT auto-discovery** (has `unique_id`) | Do NOT set | HA computes daily deltas as `current - first_reading_of_today` using `total_increasing` state class. Adding `last_reset` creates a sawtooth pattern. |
| **REST API** (no `unique_id`) | **Required** — set to midnight UTC | Without `unique_id`, HA cannot anchor the "first reading of today" calculation. Without `last_reset`, daily totals may show artificially low numbers. |

### How the Bridge Script Handles It

The production bridge sets `last_reset` dynamically on every push:

```bash
last_reset="$(date -u +%Y-%m-%d)T00:00:00Z"
```

This gives HA the same midnight anchor every time. The Energy Dashboard then computes **today's usage = current_value − last_reset_value** correctly.

### Manual last_reset on a REST Sensor

Include `last_reset` in the attributes payload on each push, set to midnight UTC:

```json
{
  "state": "6740058",
  "attributes": {
    "unit_of_measurement": "Wh",
    "device_class": "energy",
    "state_class": "total_increasing",
    "last_reset": "2026-05-28T00:00:00Z"
  }
}
```

### Detection: Is last_reset the Problem?

Compare the dashboard daily total against a known continuous load:

```bash
# Known load (e.g. UPS-reported server at 166W continuous)
daily_kwh_known=$(echo "scale=1; 166 * 24 / 1000" | bc)   # = 3.98 kWh

# Dashboard-reported total
dashboard_total_kwh=1.98  # from the Energy Dashboard UI

# If dashboard << known load, it's a stale sensor or missing last_reset
```

When the dashboard shows *less* consumption than a single known always-on load, the meter sensor is stale or lacks `last_reset`.

### How to Fix a REST Sensor with Low Daily Numbers

1. Add `last_reset` to the attributes payload (set to midnight UTC of today)
2. Wait for the next push cycle (or force one)
3. Verify: the next day's Energy Dashboard total should roughly match `(end_value - start_value) / 1000`

For a full worked example with real readings (May 2026), see `calibration-crosscheck.md`.
