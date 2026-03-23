# CLAUDE.md

## Overview

E-paper weather display for Pimoroni Inky wHAT (red, 400×300px, 3-color). Subscribes to MQTT topics and renders a weather dashboard every 15 minutes during active hours.

## Running / Deployment

```bash
# Local (Pi only — requires hardware)
python3 weather.py

# Deploy via Ansible (from dev machine)
cd /home/hirano/dev/ansible && ./deploy.sh inky
```

## Configuration (`inky.conf`, gitignored)

```ini
[ALL]
mqtt_host = <ip>
mqtt_host_port = 1883

[AWAIR]
mqtt_subs = ["Room1", "Room2"]        # local rooms
mqtt_ext_subs = ["location/Room"]     # external rooms (max 2 displayed)

[LOC]
latitude = <float>
longitude = <float>
```

## Architecture

Single file `weather.py`. MQTT callbacks store data in `g_mqtt_data` dict. Main loop updates display every 15 min on :00/:15/:30/:45 during active hours (6:30 AM–10:30 PM).

Display layout: top = outdoor temp (large) + indoor Awair sensors; bottom = forecast (max 4 items, warnings in red).

## Key Gotchas

- Some MQTT fields arrive as strings (e.g. `"temp": "65.2"`) — cast before math
- E-ink refresh is slow (~30s), especially with red pixels — avoid unnecessary redraws
- Font path `freefont/FreeSansBold.ttf` must exist relative to working dir
- `font_hanken_grotesk` imported but unused (harmless)
- External Awair rooms hard-limited to 2 (display space)
- Sunrise/sunset calculated once at startup, not updated daily

## MQTT Topics

- `weewx/sensor` — outdoor temp/humidity/wind/rain
- `purpleair/sensor` — AQI
- `weathergov/forecast` — 7-day forecast
- `weathergov/warnings` — active warnings
- `awair/*/sensor` — indoor air quality per room
