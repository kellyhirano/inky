# CLAUDE.md - AI Assistant Guide

## Project Overview

**Inky Weather Display** is a Python-based IoT weather display system designed for the Pimoroni Inky wHAT e-paper display. It aggregates real-time environmental data from multiple MQTT sources and renders a comprehensive weather dashboard on a red/black/white e-ink display.

**Primary Author**: Kelly Hirano
**License**: MIT (2020)
**Target Hardware**: Pimoroni Inky wHAT (red variant)
**Deployment Platform**: Raspberry Pi

## Repository Structure

```
/home/user/inky/
├── weather.py                          # Main application (374 lines)
├── requirements.txt                    # Python dependencies
├── inky.conf                          # Configuration file (gitignored)
├── README.md                          # Basic project documentation
├── LICENSE.md                         # MIT license
├── .gitignore                         # Git ignore patterns
└── etc/
    └── systemd/
        └── system/
            └── inky-weather.service   # systemd service definition
```

## Core Components

### 1. Main Application (`weather.py`)

**Purpose**: Long-running daemon that:
- Subscribes to MQTT topics for weather/sensor data
- Aggregates data from multiple sources
- Renders visual display on Inky wHAT e-paper screen
- Updates display every 15 minutes during active hours (7 AM - 11 PM)

**Key Functions**:

#### MQTT Callbacks
- `on_connect(client, userdata, flags, rc)` - Lines 23-40
  - Establishes MQTT subscriptions on connection
  - Subscribes to: weathergov/forecast, weathergov/warnings, weewx/sensor, purpleair/sensor, awair/*/sensor

- `on_message(client, userdata, msg)` - Lines 43-50
  - Receives MQTT messages and stores in global `g_mqtt_data` dictionary
  - All data is JSON-formatted

#### Display Rendering Functions
- `draw_outside_temp_text_line()` - Lines 53-120
  - Renders outdoor temperature (large font, top-left)
  - Shows 1-hour and 24-hour temperature deltas
  - Displays AQI (Air Quality Index) from PurpleAir
  - Shows wind gusts (if >=10)
  - Shows precipitation data (24h total and current rate)
  - Handles font scaling for temps >=100°F

- `draw_awair_text_line()` - Lines 122-158
  - Renders single-line display for Awair indoor air quality sensors
  - Shows: room initial, temperature, temp change, CO2/AQI
  - Red text warning when AQI > 100 or CO2 > 1000

- `draw_ext_awair_text_line()` - Lines 160-196
  - Renders external Awair sensors (different location)
  - Maximum 2 external rooms displayed
  - Compact format: room initial + temp or AQI

- `draw_kitchen_temp_text_line()` - Lines 198-218
  - Renders kitchen sensor data from weewx
  - Shows current time (HH:MM format)

- `draw_forecast()` - Lines 220-267
  - Renders up to 4 forecast periods
  - Priority display for weather warnings (in RED)
  - Forecast format: TIME: Description, Temp° [precip amount]
  - Text abbreviations: "BIRTHDAY" → "BDAY", day names shortened

- `paint_image()` - Lines 269-313
  - Master rendering function
  - Creates PIL Image, renders all components, pushes to display
  - Layout: Top section (outdoor temp + indoor sensors), bottom section (forecast)
  - Uses horizontal divider line at height-95

#### Main Loop
- Lines 344-374
- Sleeps 10 seconds between iterations
- Updates display only when:
  - Current hour between 7-23
  - Current minute is divisible by 15 (:00, :15, :30, :45)
  - At least 60 seconds since last update (prevents duplicate updates)

### 2. Configuration (`inky.conf`)

**Status**: Not tracked in git (see `.gitignore`)

**Required Sections**:
```ini
[ALL]
mqtt_host = <hostname>
mqtt_host_port = <port>  # default 1883

[AWAIR]
mqtt_subs = ["Room1", "Room2", ...]        # JSON array of local room names
mqtt_ext_subs = ["location/Room", ...]      # JSON array of external room paths

[LOC]
latitude = <float>
longitude = <float>
```

**Usage**:
- Lines 316-322: Configuration loading
- Lines 335-337: Latitude/longitude for sunrise/sunset calculations

### 3. Systemd Service (`etc/systemd/system/inky-weather.service`)

**Deployment Details**:
- Runs as user `pi`
- Working directory: `/home/pi/inky`
- Auto-restart on failure
- Requires network connectivity
- Standard output/error inherited (logs to journal)

## Data Schema

### MQTT Topics & Expected Formats

#### `weewx/sensor`
```json
{
  "outdoor_temperature": 43.9,
  "indoor_temperature": 70.5,
  "outdoor_humidity": 77,
  "indoor_humidity": 47,
  "outdoor_temp_change": -1.2,
  "outdoor_24h_temp_change": 2.5,
  "indoor_temp_change": -0.9,
  "rain_rate": 0.05,
  "last_day_rain": 0.15,
  "wind_gust": 12
}
```

#### `purpleair/sensor`
```json
{
  "st_aqi": 45,
  "st_lrapa_aqi": 42,
  "st_aqi_last_hour": -3,
  "st_lrapa_aqi_last_hour": -2,
  "st_aqi_desc": "Good"
}
```

#### `awair/{room}/sensor`
```json
{
  "location": "Family Room",
  "temp": "65.2",
  "humid": "48",
  "co2": 517.0,
  "voc": 109.0,
  "dust": "1.0",
  "aqi": 6,
  "datetime": "2020-04-04T05:29:59.805Z",
  "last_hour_temp": -0.5
}
```

#### `weathergov/forecast`
```json
[
  {
    "day": "TONIGHT",
    "forecast": "Chance rain",
    "temp": "50",
    "precip_chance": "60",
    "precip_amount": "0.1-0.2\"",
    "precip_severity": 2
  }
]
```

#### `weathergov/warnings`
```json
[
  {
    "title": "WINTER STORM WARNING",
    "desc": "Heavy snow expected"
  }
]
```

## Code Conventions

### Style
- **PEP 8 compliant** (see commits 1ff69bf, bb1408d)
- Functions use descriptive names with underscores
- Global variables prefixed with `g_`
- Four-space indentation
- Maximum line length: ~80 characters (visual alignment in display code)

### Patterns
- **Global state management**: All MQTT data stored in `g_mqtt_data` dictionary
- **Color constants**: Access via `inky_display.BLACK`, `inky_display.RED`, `inky_display.WHITE`
- **Font loading**: Uses freefont/FreeSansBold.ttf at various sizes (18, 20, 72, 96)
- **Coordinate-based layout**: All drawing uses absolute pixel positioning
- **Conditional display**: Only render elements when data exists or thresholds met

### Error Handling
- **Minimal**: Code assumes MQTT data availability
- **Defensive checks**:
  - Lines 132-133: Check for `last_hour_temp` existence
  - Lines 135-137: Check for `aqi` existence
  - Lines 127, 169, 203: Check if MQTT topic exists in data
  - Lines 193-195: Limit external rooms to 2

### Common Pitfalls
1. **Temperature >= 100**: Special font sizing logic (lines 67-70)
2. **String vs numeric types**: Some MQTT data arrives as strings (e.g., `"temp": "65.2"`)
3. **Display refresh time**: Red pixel updates are SLOW (~30 seconds), avoid frequent redraws
4. **Time-based updates**: Display only updates on :00, :15, :30, :45 past the hour

## Development Workflow

### Local Development
1. Install dependencies: `pip install -r requirements.txt`
2. Additional requirements (not in requirements.txt):
   - `inky` library (Pimoroni)
   - `font_hanken_grotesk` (imported but unused in current code)
   - `suntime` library for sunrise/sunset
3. Create `inky.conf` with proper MQTT configuration
4. Run directly: `python3 weather.py`

### Testing
- **No automated tests** exist in repository
- Manual testing requires:
  - MQTT broker with test data
  - Physical Inky wHAT display OR mock library
  - Test during active hours (7 AM - 11 PM) or modify time checks

### Deployment
1. Copy files to `/home/pi/inky/` on Raspberry Pi
2. Create `inky.conf` with production settings
3. Install systemd service:
   ```bash
   sudo cp etc/systemd/system/inky-weather.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable inky-weather.service
   sudo systemctl start inky-weather.service
   ```
4. Monitor: `sudo journalctl -u inky-weather -f`

## Git Workflow

### Branch Strategy
- Main development on `main` branch
- Feature branches use pattern: `claude/description-XXXXX`
- Current branch: `claude/add-claude-documentation-UrLFH`

### Commit Message Patterns (from history)
- Descriptive, lowercase, no period
- Examples:
  - "added check for existence of last_hour_temp and cleaned up BIRTHDAY in forecast"
  - "fixed regex for abbreviating day of week"
  - "added precip amounts to forecast, minor formatting changes"
  - "initial checkin" (for new features)

### Push Procedure
```bash
git push -u origin claude/add-claude-documentation-UrLFH
```

## Dependencies

### Python Packages (requirements.txt)
- `paho-mqtt~=1.5.0` - MQTT client library
- `fonts-freefont-ttf~=20120503-9` - Font package (Debian package name)

### Additional Python Dependencies (not in requirements.txt)
- `pillow` (PIL fork) - Image manipulation
- `inky` - Pimoroni Inky display library
- `font-hanken-grotesk` - Font library (imported line 12, unused)
- `suntime` - Sunrise/sunset calculations

### System Dependencies
- `/usr/bin/python3` - Python 3 interpreter
- TrueType fonts in `freefont/FreeSansBold.ttf` (relative to working dir)

## Key Technical Details

### Display Specifications
- **Resolution**: 400x300 pixels (landscape)
- **Colors**: 3-color (black, white, red)
- **Refresh time**: ~15-30 seconds (slower with red pixels)
- **Display object**: `InkyWHAT("red")`

### Timing & Scheduling
- **Main loop interval**: 10 seconds
- **Display update interval**: 15 minutes (:00, :15, :30, :45)
- **Active hours**: 7:00 AM - 11:00 PM (lines 356-358)
- **Duplicate prevention**: 60-second cooldown between updates

### Font Sizes
- Giant: 96pt (outdoor temp when < 100°)
- Large: 72pt (outdoor temp when >= 100°)
- Regular: 20pt (indoor sensors, time)
- Small: 18pt (deltas, forecast, AQI)

### Layout Dimensions
- **Outdoor temp**: (7, 0) - top-left corner
- **Indoor sensors**: (175, 7) - right column
- **Forecast divider**: height - 95 pixels from bottom
- **Forecast start**: height - 110 pixels from bottom
- **Max forecast items**: 4 (with warnings taking priority)

## AI Assistant Guidelines

### When Modifying Code

1. **Preserve display timing logic**: Don't change the 7-23 hour window or :15 minute intervals without explicit request
2. **Maintain MQTT topic structure**: Changes to topics require coordination with upstream data publishers
3. **Test with representative data**: Use sample data from lines 363-373 when testing without hardware
4. **Consider display refresh cost**: Each `inky_display.show()` takes 15-30 seconds
5. **Font path dependencies**: Code assumes `freefont/FreeSansBold.ttf` exists in working directory
6. **Configuration changes**: Update both code AND document required `inky.conf` changes

### Code Quality Standards

- Follow existing PEP 8 style
- Add defensive checks for new MQTT data fields (check existence before access)
- Use meaningful variable names (current style: descriptive underscored names)
- Comment complex pixel calculations or layout logic
- Maintain the functional decomposition (one function per display section)

### Common Tasks

#### Adding New Sensor Data
1. Add MQTT topic subscription in `on_connect()`
2. Create new `draw_*()` function following existing patterns
3. Call from `paint_image()` with appropriate coordinates
4. Update this CLAUDE.md with data schema

#### Changing Display Layout
1. Identify affected `draw_*()` functions
2. Adjust `start_x`, `start_y` coordinates
3. Test with representative data
4. Verify no overlap with other display sections

#### Modifying Forecast Display
1. Edit `draw_forecast()` function (lines 220-267)
2. Respect `max_items = 4` limit (vertical space constraint)
3. Preserve warning priority (warnings display before forecast)
4. Test text abbreviation regex patterns

### Testing Without Hardware

Mock the Inky display library:
```python
class MockInkyWHAT:
    WIDTH = 400
    HEIGHT = 300
    BLACK = 0
    WHITE = 1
    RED = 2
    def __init__(self, color): pass
    def set_image(self, img):
        img.save('test_output.png')  # Save for visual inspection
    def show(self): pass
```

### Important Gotchas

1. **Line 7**: Duplicate `import json` (harmless but redundant)
2. **Line 12**: `font_hanken_grotesk` imported but never used
3. **Lines 132-133, 135-137**: Defensive checks added later - follow this pattern for new fields
4. **Line 247**: Regex handles special "BIRTHDAY" string in forecast (specific to user's weather source)
5. **Lines 193-195**: Hard limit of 2 external rooms for space reasons
6. **Sunset/sunrise calculation** (lines 339-342): Calculated once at startup, not updated daily

## Recent Changes (Last 5 Commits)

1. `581dbe0` - Added existence check for `last_hour_temp`, cleaned up BIRTHDAY regex
2. `ee2d5c8` - Fixed day-of-week abbreviation regex
3. `3ae302a` - Added precipitation amounts to forecast, exploring sunrise/sunset
4. `eb4c78a` - Initial checkin (of what?)
5. `9eaa94d` - Added LRAPA AQI reading, consolidated PurpleAir topics, limited external rooms to 2

## Questions to Ask Before Making Changes

1. Will this change affect the MQTT data schema? (Coordinate with data publishers)
2. Does this change require hardware testing? (E-ink display behavior)
3. Will this impact display refresh time? (Already slow with red pixels)
4. Does this require `inky.conf` updates? (Document them)
5. Is this change timezone-aware? (Code uses `time.tzset()` line 331)
6. Will this work during all hours or only active hours? (Current: 7 AM - 11 PM)

## Future Considerations

Based on code exploration:

1. **Sunrise/sunset times**: Calculated lines 339-342 but not displayed yet
2. **Daily sunrise update**: Currently calculated once at startup
3. **Font dependency**: `font_hanken_grotesk` imported but unused - remove or integrate?
4. **Error handling**: Minimal error handling for MQTT connection failures
5. **Configuration validation**: No validation of `inky.conf` values
6. **Logging**: Only prints to stdout (captured by systemd journal)

## Resources

- **Pimoroni Inky wHAT**: https://shop.pimoroni.com/products/inky-what
- **Paho MQTT**: https://www.eclipse.org/paho/
- **PIL/Pillow**: https://pillow.readthedocs.io/
- **Systemd**: For service management and logs

---

*This documentation was generated on 2026-01-02 for commit `581dbe0` on branch `claude/add-claude-documentation-UrLFH`*
