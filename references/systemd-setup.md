# Systemd Timer Setup

The bridge can run automatically every 5 minutes via a systemd user timer.

## Service Unit

Create `~/.config/systemd/user/rtlamr-ha-bridge.service`:

```
[Unit]
Description=rtlamr → Home Assistant power meter bridge
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=%h/projects/rtlamr-ha-bridge/rtlamr-ha-bridge.sh
EnvironmentFile=%h/.config/rtlamr-ha-bridge.env
StandardOutput=journal
StandardError=journal
```

## Timer Unit

Create `~/.config/systemd/user/rtlamr-ha-bridge.timer`:

```
[Unit]
Description=rtlamr → HA bridge (every 5 minutes)

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
RandomizedDelaySec=30
AccuracySec=1min

[Install]
WantedBy=timers.target
```

## Enable

```bash
systemctl --user daemon-reload
systemctl --user enable --now rtlamr-ha-bridge.timer
```

## Reboot Survival

The systemd user timer runs as your user and starts after login. To make it start on boot without a login session, enable lingering:

```bash
sudo loginctl enable-linger $(whoami)
```

Without this, the timer won't fire after a reboot until you SSH in or log in at the console.
