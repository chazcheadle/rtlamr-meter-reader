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
