# MQTT Auto-Discovery Setup

Requires a Mosquitto broker and `paho-mqtt`:

```bash
pip3 install paho-mqtt
```

## Broker Setup

```bash
sudo apt-get install -y mosquitto mosquitto-clients
sudo mosquitto_passwd -c /etc/mosquitto/passwd rtlamr
sudo tee /etc/mosquitto/conf.d/rtlamr.conf <<'EOF'
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
persistence true
persistence_location /var/lib/mosquitto/
EOF
sudo systemctl enable --now mosquitto
```

## HA Auto-Discovery Topics

```
homeassistant/sensor/rtlamr_{meter_id}/config   (retained, published once)
homeassistant/sensor/rtlamr_{meter_id}/state     (published every reading)
```

### Config Payload

Publish once with `--retain` so it survives broker restarts:

```bash
mosquitto_pub -h localhost -u rtlamr -P <password> -t \
  "homeassistant/sensor/rtlamr_${METER_ID}/config" -r -m \
  "{\"name\":\"Power Meter\",\"state_topic\":\"homeassistant/sensor/rtlamr_${METER_ID}/state\",\
  \"unit_of_measurement\":\"Wh\",\"device_class\":\"energy\",\"state_class\":\"total_increasing\",\
  \"unique_id\":\"rtlamr_${METER_ID}\",\"device\":{\"identifiers\":[\"rtlamr_${METER_ID}\"],\
  \"name\":\"Itron Power Meter\",\"manufacturer\":\"Itron\"}}"
```

### State Payload

The state payload is just the bare integer consumption value.

## MQTT Bridge Script

See `scripts/rtlamr-mqtt-bridge.py` for a Python MQTT bridge that handles discovery config + state publishing.
