# Repository Guidelines

## Project Structure & Module Organization
This repo is a single-purpose Python 3 app for the Pimoroni Inky wHAT e-paper display.

- `weather.py`: main daemon that subscribes to MQTT topics and renders the dashboard.
- `requirements.txt`: Python dependencies.
- `etc/systemd/system/inky-weather.service`: service definition for boot startup.
- `inky.conf`: runtime config (not tracked).

## Build, Test, and Development Commands
- Install deps (on Raspberry Pi): `sudo pip3 install -r requirements.txt`.
- Run locally: `python3 weather.py`.
- Enable service: `sudo cp etc/systemd/system/inky-weather.service /etc/systemd/system/` and `sudo systemctl enable --now inky-weather`.

## Coding Style & Naming Conventions
- Python 3, 4-space indentation, snake_case for functions, globals prefixed with `g_`.
- Config file uses INI format with sections like `[ALL]`, `[AWAIR]`, `[LOC]`.
- Keep rendering changes isolated to drawing helpers to avoid breaking layout.

## MQTT Topics
| Topic | Purpose |
| --- | --- |
| `weewx/sensor` | Outdoor/indoor temps, wind, rain. |
| `purpleair/sensor` | AQI values and deltas. |
| `weathergov/forecast` | Short-term forecast data. |
| `weathergov/warnings` | Alert headlines. |
| `awair/<room>/sensor` | Indoor air quality by room. |

## Testing Guidelines
- No automated tests; validate with live MQTT data and physical hardware.
- Display updates occur every 15 minutes during active hours (7 AM–11 PM); verify schedule changes carefully.

## Commit & Pull Request Guidelines
- Use short, imperative commit messages (“Add forecast warning handling”).
- PRs should list MQTT topics touched, example payloads, and the hardware used for validation.
- Note any config or font dependency changes in `README.md`.

## Configuration & Ops Notes
- `inky.conf` must define MQTT host/port and Awair room lists; update docs when adding new config keys.
