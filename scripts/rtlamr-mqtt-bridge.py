#!/usr/bin/env python3
"""rtlamr → MQTT → Home Assistant auto-discovery bridge

Reads meter consumption from a file produced by the existing rtlamr capture,
then publishes the reading to MQTT with HA auto-discovery.

Designed as a companion to rtlamr-ha-bridge.sh — the REST API script
handles the SDR capture, this script handles MQTT publishing. Hook it
into the bridge as:

    READING=$(./rtlamr-ha-bridge.sh --dry-run)
    ./rtlamr-mqtt-bridge.py "$READING"

Or run standalone if you build your own capture loop.

Environment:
    METER_ID     (required)   — Your meter ID, e.g. 12345678
    MQTT_PASS    (required)   — MQTT broker password
    MQTT_HOST    (default: localhost)
    MQTT_PORT    (default: 1883)
    MQTT_USER    (default: rtlamr)
    HA_PREFIX    (default: homeassistant)
"""

import json
import os
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

# -- Config ----------------------------------------------------------------

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "rtlamr")
MQTT_PASS = os.environ.get("MQTT_PASS", "")
METER_ID_STR = os.environ.get("METER_ID", "")
HA_PREFIX = os.environ.get("HA_PREFIX", "homeassistant")

if not METER_ID_STR:
    print("ERROR: METER_ID not set. Set it to your meter ID (run a discovery scan first).")
    sys.exit(1)

try:
    METER_ID = int(METER_ID_STR)
except ValueError:
    print(f"ERROR: METER_ID must be a number, got: {METER_ID_STR}")
    sys.exit(1)

CONFIG_FLAG = Path(f"/tmp/rtlamr_mqtt_config_sent_{METER_ID}")


# -- Discovery payload -----------------------------------------------------

def discovery_topic(meter_id):
    return f"{HA_PREFIX}/sensor/rtlamr_{meter_id}/config"

def state_topic(meter_id):
    return f"{HA_PREFIX}/sensor/rtlamr_{meter_id}/state"

def build_discovery_payload(meter_id):
    topic = state_topic(meter_id)
    return {
        "name": "Power Meter",
        "state_topic": topic,
        "unit_of_measurement": "Wh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "unique_id": f"rtlamr_{meter_id}",
        "device": {
            "identifiers": [f"rtlamr_{meter_id}"],
            "name": "Itron Power Meter",
            "manufacturer": "Itron",
        },
    }


# -- Main ------------------------------------------------------------------

def main():
    if not MQTT_PASS:
        print("SKIP: MQTT_PASS not set")
        sys.exit(0)

    reading = sys.argv[1] if len(sys.argv) > 1 else None
    if not reading:
        print("Usage: rtlamr-mqtt-bridge.py <consumption_wh>")
        print("   or: ./rtlamr-ha-bridge.sh --dry-run | xargs rtlamr-mqtt-bridge.py")
        sys.exit(1)

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    # Publish state
    st = state_topic(METER_ID)
    client.publish(st, reading)
    print(f"MQTT: published {reading} Wh to {st}")

    # Publish discovery config (one-shot, retained)
    if not CONFIG_FLAG.exists():
        dt = discovery_topic(METER_ID)
        payload = json.dumps(build_discovery_payload(METER_ID))
        client.publish(dt, payload, retain=True)
        print(f"MQTT: published auto-discovery config to {dt}")
        CONFIG_FLAG.touch()

    client.disconnect()


if __name__ == "__main__":
    main()
