# SQLite Backend

For DIY analysis — every 5-minute reading is logged to a local SQLite database.

## Schema

```bash
mkdir -p ~/meter-data

sqlite3 ~/meter-data/meter.db <<'SQL'
CREATE TABLE IF NOT EXISTS readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    meter_id    INTEGER NOT NULL,
    consumption_wh INTEGER NOT NULL,
    captured_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_readings_meter ON readings(meter_id);
CREATE INDEX IF NOT EXISTS idx_readings_time ON readings(captured_at);
SQL
```

## Insert a Reading

```bash
sqlite3 ~/meter-data/meter.db \
  "INSERT INTO readings(meter_id, consumption_wh, captured_at) \
   VALUES(${METER_ID}, $READING, '$(date -u +%Y-%m-%dT%H:%M:%SZ)');"
```

## Query Recent Data

### Last 24 Hours

```bash
sqlite3 ~/meter-data/meter.db \
  "SELECT captured_at, consumption_wh FROM readings \
   WHERE meter_id=${METER_ID} AND created_at >= datetime('now', '-1 day') \
   ORDER BY created_at;"
```

### Average Power Over 7 Days

```bash
sqlite3 ~/meter-data/meter.db \
  "SELECT r.captured_at,
          (r.consumption_wh - COALESCE(p.consumption_wh, r.consumption_wh)) AS delta_wh,
          ROUND((r.consumption_wh - COALESCE(p.consumption_wh, r.consumption_wh)) * 12.0) AS avg_watts
   FROM readings r
   LEFT JOIN readings p ON p.id = (
       SELECT MAX(id) FROM readings WHERE id < r.id AND meter_id=r.meter_id
   )
   WHERE r.meter_id=${METER_ID} AND r.created_at >= datetime('now', '-7 days')
   ORDER BY r.created_at;"
```
