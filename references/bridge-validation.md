     1|# Bridge Reading Validation — RTLAMR → HA
     2|
     3|A ~3.6 MWh spike from a neighbor meter corrupted the Energy Dashboard statistics. This document captures the validation gaps found during root cause analysis.
     4|
     5|## Validation Rules
     6|
     7|The bridge's `get_reading()` iterates rtlamr JSON output and picks the **last** value it sees. This has zero validation — four specific gaps were found:
     8|
     9|### 1. No Meter ID Filter
    10|
    11|Both SCM and IDM carry identifiers:
    12|
    13|```python
    14|# SCM
    15|msg["Message"]["ID"]                   # = <YOUR_METER_ID> (your meter)
    16|# IDM
    17|msg["Message"]["ERTSerialNumber"]      # = <YOUR_METER_ID>
    18|```
    19|
    20|But the bridge doesn't check them. A neighbor's meter transmission during the 50s window overwrites your reading. **Fix:** skip all messages where `ID` / `ERTSerialNumber` doesn't match your meter.
    21|
    22|### 2. No Max-Delta Sanity Check
    23|
    24|A reading jumping from 6,731,719 Wh → 3,657,608 Wh → 6,731,752 Wh in 10 minutes (a 3M Wh swing) passes through silently.
    25|
    26|For a `total_increasing` sensor in HA:
    27|- On a **drop** (current < previous) — HA's statistics engine freezes `sum` (doesn't subtract), creating a plateau rather than a dip
    28|- On a **recovery jump back up** (previous state level) — HA sees the full delta as new consumption, adding ~3M Wh to the cumulative `sum`
    29|- That contaminated `sum` propagates into every subsequent hourly rollup
    30|
    31|**Fix:** reject any delta > MAX_DELTA_WH (recommended: 50,000 Wh = ~600 kW sustained, generous enough for real usage but catches multi-MWh spikes).
    32|
    33|### 3. No Stale IDM Rejection
    34|
    35|The IDM (Interval Data Message) provides 47 × 5-minute differential intervals covering ~4 hours of history. `LastConsumptionCount` is the cumulative total AT the **start** of the last 5-minute interval — it LAGS behind the SCM's real-time `Consumption` by up to 5 minutes.
    36|
    37|Problems:
    38|- If the SCM packet arrives *before* the IDM in the scan, the final `wh` is the stale `LastConsumptionCount` — causing a small apparent regression
    39|- The meter may report `ConsumptionIntervalCount=75` (not 47), meaning the interval buffer varies by model or module state. Hardcoding assumptions breaks.
    40|- IDM is useful for computing historical deltas but **should not be the preferred source** for real-time pushing
    41|
    42|**Fix:** prefer SCM `Consumption` over IDM `LastConsumptionCount`. Only use IDM as a fallback if no SCM was captured.
    43|
    44|### 4. SCM/IDM Interleaving
    45|
    46|rtlamr outputs packets in decode order — whichever arrives last wins. In a single 50s window, the sequence might be SCM→SCM→IDM (IDM wins) or IDM→SCM (SCM wins). This is non-deterministic and can cause small reading regressions cycle-to-cycle.
    47|
    48|**Fix:** iterate all packets, track the best SCM value and best IDM value separately, then prefer SCM.
    49|
    50|## Recommended Python Validation Logic
    51|
    52|Replace the Python one-liner in `get_reading()` with:
    53|
    54|```python
    55|TARGET_METER = <YOUR_METER_ID>
    56|MAX_DELTA_WH = 50000
    57|previous_value = None
    58|wh = None
    59|
    60|with open('/tmp/rtlamr_output.json') as f:
    61|    for line in f:
    62|        line = line.strip()
    63|        if not line or line.startswith('C:'):
    64|            continue
    65|        try:
    66|            msg = json.loads(line)
    67|            m = msg.get('Message', {})
    68|            mid = m.get('ID', m.get('ERTSerialNumber'))
    69|            if mid != TARGET_METER:
    70|                continue
    71|            t = msg.get('Type')
    72|            if t == 'SCM':
    73|                candidate = m.get('Consumption')
    74|            elif t == 'IDM':
    75|                # Only use IDM as fallback if no SCM yet
    76|                if wh is not None:
    77|                    continue
    78|                candidate = m.get('LastConsumptionCount')
    79|            else:
    80|                continue
    81|
    82|            if candidate is not None:
    83|                if previous_value is not None:
    84|                    delta = candidate - previous_value
    85|                    if abs(delta) > MAX_DELTA_WH:
    86|                        print(f'SKIP (delta {delta} Wh exceeds {MAX_DELTA_WH})', flush=True)
    87|                        continue
    88|                previous_value = candidate
    89|                wh = candidate
    90|        except json.JSONDecodeError:
    91|            pass
    92|```
    93|
    94|This:
    95|- Filters by meter ID (no neighbor interference)
    96|- Prefers SCM over IDM (no stale readings)
    97|- Rejects impossible deltas (no spike propagation)
    98|- Still allows normal consumption patterns
    99|
   100|## Verification
   101|
   102|After applying, watch the systemd journal for validation skip messages:
   103|
   104|```bash
   105|journalctl --user -u rtlamr-ha-bridge.service -f | grep -i skip
   106|```
   107|
   108|Expected: normal ops show no skips. If a spike occurs (neighbor transmission, decode glitch), the skip is logged instead of poisoning HA statistics.
   109|