#!/bin/bash
# rtlamr → Home Assistant REST API bridge
#
# Itron ERT smart meter reader. Designed as a systemd oneshot for timer-driven
# execution every 5 minutes. Uses HA REST API (not MQTT) to bypass MQTT credential
# discovery problems. Sensor entity must have device_class: energy and
# state_class: total_increasing for the Energy Dashboard.
#
# All configuration via environment variables (EnvironmentFile or export):
#
#   Required:
#     HASS_TOKEN                  HA long-lived access token
#     METER_ID                    Your meter ID (e.g. 12345678)
#
#   Optional:
#     HASS_URL                    HA URL (default: http://homeassistant:8123)
#     RTLTCP_SERVER               rtl_tcp host:port (default: localhost:1234)
#     RTLAMR_GAIN                 Gain index for R820T (default: 10)
#     SENSOR_ID                   HA sensor entity name (default: sensor.rtlamr_power_meter)
#     SCAN_DURATION               Capture window in seconds (default: 50)
#
# Usage:
#   ./rtlamr-ha-bridge.sh           # one-shot, pushes to HA
#   ./rtlamr-ha-bridge.sh --dry-run # print reading, no HA push

set -e

RTLAMR="${HOME}/.local/bin/rtlamr"
RTL_TCP_SERVER="${RTLTCP_SERVER:-localhost:1234}"
GAIN_BY_INDEX="${RTLAMR_GAIN:-10}"
HASS_URL="${HASS_URL:-http://homeassistant:8123}"
# Ensure URL has scheme for Python's urllib
case "$HASS_URL" in
    http://*) ;;
    https://*) ;;
    *) HASS_URL="http://${HASS_URL}" ;;
esac
export HASS_URL

HASS_TOKEN="${HASS_TOKEN:-}"
SENSOR_ID="${SENSOR_ID:-sensor.rtlamr_power_meter}"
METER_ID="${METER_ID:-}"
TMPFILE="/tmp/rtlamr_output.json"
# 50s scan guarantees at least one SCM/IDM burst (meter transmits ~every 30-60s)
DURATION="${SCAN_DURATION:-50}"
TIMEOUT=$((DURATION + 15))

# Validate
if [ -z "$METER_ID" ]; then
    echo "ERROR: METER_ID not set. Set it to your meter ID (run a discovery scan first)."
    exit 1
fi

get_reading() {
    # Retry up to 2 times with 15s gap
    for attempt in 1 2; do
        timeout "$TIMEOUT" "$RTLAMR" \
            -server="$RTL_TCP_SERVER" \
            -msgtype=scm,idm \
            -gainbyindex="$GAIN_BY_INDEX" \
            -agcmode=true \
            "-duration=${DURATION}s" \
            -format=json \
            > "$TMPFILE" 2>/dev/null

        wh=$(python3 -c "
import json, os
METER_ID = int(os.environ.get('METER_ID', '0'))
wh = None
with open('$TMPFILE') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('C:'):
            continue
        try:
            msg = json.loads(line)
            m = msg.get('Message', {})
            if msg.get('Type') == 'SCM':
                if m.get('ID') == METER_ID:
                    wh = m.get('Consumption')
            elif msg.get('Type') == 'IDM':
                if m.get('ERTSerialNumber') == METER_ID:
                    wh = m.get('LastConsumptionCount')
        except json.JSONDecodeError:
            pass
if wh is not None:
    print(wh)
" 2>/dev/null)

        if [ -n "$wh" ]; then
            echo "$wh"
            return 0
        fi
        sleep 15
    done
    echo "NO_DATA"
    return 1
}

push_to_ha() {
    local wh="$1"
    python3 -c "
import json, os, sys, urllib.request, urllib.error
token = os.environ.get('HASS_TOKEN', '')
if not token:
    print('SKIP: no HASS_TOKEN')
    exit(0)
url = os.environ.get('HASS_URL', 'http://homeassistant:8123') + '/api/states/${SENSOR_ID}'
data = json.dumps({
    'state': '$wh',
    'attributes': {
        'unit_of_measurement': 'Wh',
        'device_class': 'energy',
        'state_class': 'total_increasing',
        'friendly_name': 'Power Meter',
        'meter_id': int(os.environ.get('METER_ID', '0')),
        'rtl_tcp': '${RTL_TCP_SERVER}',
        'last_updated': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
    }
}).encode()
try:
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }, method='POST')
    resp = urllib.request.urlopen(req, timeout=10)
    body = json.loads(resp.read())
    print(f'HA {resp.status}: state={body.get(\"state\",\"?\")}')
except urllib.error.HTTPError as e:
    print(f'HA error {e.code}')
    sys.exit(1)
except urllib.error.URLError as e:
    print(f'HA unreachable: {e.reason}')
    sys.exit(1)
except Exception as e:
    print(f'HA error: {e}')
    sys.exit(1)
" 2>/dev/null
}

# --- Main ---
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
    esac
done

READING=$(get_reading)

if [ "$READING" = "NO_DATA" ]; then
    echo "No meter data received (will retry next cycle)"
    exit 0  # Exit clean so systemd doesn't mark as failed
fi

KWH=$(echo "scale=1; $READING / 1000" | bc)
echo "Meter ${METER_ID}: ${READING} Wh (${KWH} kWh)"

if [ "$DRY_RUN" = false ] && [ -n "$HASS_TOKEN" ]; then
    push_to_ha "$READING"
fi
