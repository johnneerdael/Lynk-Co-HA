# Lynk & Co Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/johnneerdael/Lynk-Co-HA)](https://github.com/johnneerdael/Lynk-Co-HA/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A custom Home Assistant integration for Lynk & Co vehicles. Monitor your vehicle's status, control climate, locks, and more directly from Home Assistant.

> **⚠️ European Models Only**: This integration has only been tested with European Lynk & Co models.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [HACS Installation (Recommended)](#hacs-installation-recommended)
  - [Manual Installation](#manual-installation)
- [Configuration](#configuration)
  - [Step 1: Start the Integration Setup](#step-1-start-the-integration-setup)
  - [Step 2: Authenticate via Browser](#step-2-authenticate-via-browser)
  - [Step 3: Complete Setup](#step-3-complete-setup)
- [Smart Polling System](#smart-polling-system)
  - [How It Works](#how-it-works)
  - [Configuration Options](#configuration-options)
  - [Legacy Polling Mode](#legacy-polling-mode)
- [Services](#services)
  - [Climate Control](#climate-control)
  - [Door Control](#door-control)
  - [Horn & Lights](#horn--lights)
  - [Engine Control (Experimental)](#engine-control-experimental)
  - [Utility Services](#utility-services)
- [Entities](#entities)
  - [Binary Sensors](#binary-sensors)
  - [Lock Entity](#lock-entity)
  - [Device Tracker](#device-tracker)
  - [Sensors Overview](#sensors-overview)
- [Sensor State Values](#sensor-state-values)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- 🚗 **Vehicle Monitoring**: Battery level, fuel level, odometer, temperatures, and more
- 🔒 **Lock Control**: Lock and unlock your vehicle remotely
- ❄️ **Climate Control**: Start and stop pre-conditioning
- 📍 **Location Tracking**: Track your vehicle's position with address resolution
- 🔊 **Horn & Lights**: Flash lights or honk remotely to locate your vehicle
- ⚡ **Smart Polling**: Adaptive data refresh based on charging status and time of day
- 🔋 **EV Charging**: Monitor charging status, time to full charge, and battery range

---

## Installation

### HACS Installation (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on **Integrations**
3. Click the **⋮** menu (three dots) in the top right corner
4. Select **Custom repositories**
5. Add the repository URL: `https://github.com/johnneerdael/Lynk-Co-HA`
6. Select **Integration** as the category
7. Click **Add**
8. Search for "Lynk & Co" in HACS and click **Install**
9. **Restart Home Assistant**

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/johnneerdael/Lynk-Co-HA/releases)
2. Extract the `lynkco` folder to your `custom_components` directory
3. Your folder structure should look like: `config/custom_components/lynkco/`
4. **Restart Home Assistant**

---

## Configuration

Due to Lynk & Co's authentication system using CAPTCHA protection, this integration uses a **browser-based redirect login** method. You'll complete the login in your browser and copy a redirect URL back to Home Assistant.

### Step 1: Start the Integration Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Lynk & Co** and select it
3. Enter your **Vehicle Identification Number (VIN)**
   - You can find this in your Lynk & Co app or on your vehicle documents
4. Click **Submit**

### Step 2: Authenticate via Browser

1. A **login link** will be displayed - click it to open in your browser
2. Complete the Lynk & Co login process (including any CAPTCHA and 2FA)
3. After successful login, your browser will redirect to a URL starting with:
   ```
   msauth.com.lynkco.prod.lynkco-app://auth?code=...
   ```
4. **Copy the entire redirect URL** from your browser's address bar

> **💡 Pro Tip**: In your browser's Developer Tools (F12), go to the **Network** tab and filter for `msauth://prod.lynkco.app.crisp.prod/` - the only request that appears will be the one you need. Copy the complete **Request URL**.

### Step 3: Complete Setup

1. Paste the copied redirect URL into the Home Assistant configuration field
2. Click **Submit**
3. The integration will extract the authentication tokens and complete setup

> **Note**: The first data fetch is always performed immediately after setup, regardless of time restrictions.

---

## Smart Polling System

The integration includes an intelligent polling system designed to minimize API calls while ensuring fresh data when you need it most (e.g., during EV charging).

### How It Works

| Time Period | Condition | Polling Interval |
|------------|-----------|------------------|
| **Active Hours** | Normal operation | 20-40 minutes (randomized) |
| **Active Hours** | Charger connected + Battery < target | 8-12 minutes (randomized) |
| **Dark Hours** | Outside active hours | No polling until next active period |
| **Any Time** | Manual `force_update_data` | Immediate update |

**Key behaviors:**
- **Randomized intervals**: Polling times are randomized within ranges to avoid predictable API patterns
- **Randomized active hours**: Start/end times have a random 0-20 minute offset (changes daily)
- **Charging detection**: Faster polling when `charger_connection_status` is `CHARGER_CONNECTION_CONNECTED_WITH_POWER` AND battery is below target
- **Initial setup**: First data fetch always runs, regardless of time restrictions

### Configuration Options

Access these options via **Settings** → **Devices & Services** → **Lynk & Co** → **Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| **Enable Smart Polling** | On | Toggle between smart polling and legacy fixed-interval mode |
| **Active Hours Start** | 10 | Hour when active polling begins (plus random 0-20 min offset) |
| **Active Hours End** | 22 | Hour when active polling ends (plus random 0-20 min offset) |
| **Normal Interval Min** | 20 | Minimum minutes between updates during active hours |
| **Normal Interval Max** | 40 | Maximum minutes between updates during active hours |
| **Charging Interval Min** | 8 | Minimum minutes between updates while charging |
| **Charging Interval Max** | 12 | Maximum minutes between updates while charging |
| **Charging Target %** | 90 | Battery percentage above which normal intervals resume |

### Legacy Polling Mode

When smart polling is disabled, the integration uses the legacy fixed-interval system:

| Option | Default | Description |
|--------|---------|-------------|
| **Scan Interval** | 120 | Minutes between data updates (15-1440) |
| **Dark Hours Start** | 1 | Hour when automatic updates pause |
| **Dark Hours End** | 4 | Hour when automatic updates resume |

---

## Services

All services are available under the `lynkco` domain.

### Climate Control

#### `lynkco.start_climate`
Starts the vehicle's pre-conditioning system.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `climate_level` | No | `MEDIUM` | Intensity: `LOW`, `MEDIUM`, or `HIGH` |
| `duration_in_minutes` | No | `15` | Duration in minutes (1-30) |

```yaml
service: lynkco.start_climate
data:
  climate_level: HIGH
  duration_in_minutes: 20
```

#### `lynkco.stop_climate`
Stops the pre-conditioning system.

```yaml
service: lynkco.stop_climate
```

### Door Control

#### `lynkco.lock_doors`
Locks all vehicle doors and trunk.

```yaml
service: lynkco.lock_doors
```

#### `lynkco.unlock_doors`
Unlocks all vehicle doors and trunk. Doors auto-relock after 15 seconds if not opened.

```yaml
service: lynkco.unlock_doors
```

### Horn & Lights

#### `lynkco.start_flash_lights`
Activates the hazard lights/turn signals.

#### `lynkco.stop_flash_lights`
Deactivates the hazard lights.

#### `lynkco.start_honk`
Activates the horn.

#### `lynkco.stop_honk`
Stops the horn.

#### `lynkco.start_honk_flash`
Activates both horn and hazard lights simultaneously.

### Engine Control (Experimental)

> **⚠️ Warning**: These features are experimental and not officially supported by Lynk & Co. Enable "Experimental Features" in options to use them.

#### `lynkco.start_engine`
Remotely starts the engine. On EV/hybrid models, this starts the EV system and enables climate with your last settings.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `duration_in_minutes` | No | `15` | Maximum runtime (1-15 minutes) |

**Known limitations:**
- May not work with insufficient fuel in the tank
- Behavior with low EV battery is untested

#### `lynkco.stop_engine`
Stops the engine if started remotely.

### Utility Services

#### `lynkco.force_update_data`
Forces an immediate data refresh, bypassing all time restrictions (dark hours/smart polling).

```yaml
service: lynkco.force_update_data
```

#### `lynkco.refresh_tokens`
Manually refreshes authentication tokens. Usually not needed as this is handled automatically.

---

## Entities

### Binary Sensors

| Entity | Description | On State |
|--------|-------------|----------|
| `binary_sensor.lynk_co_pre_climate_active` | Pre-conditioning status | Climate running |
| `binary_sensor.lynk_co_vehicle_is_running` | Engine/EV system status | Vehicle running |
| `binary_sensor.lynk_co_position_is_trusted` | GPS position reliability | Position accurate |

### Lock Entity

| Entity | Description |
|--------|-------------|
| `lock.lynk_co_locks` | Central locking control - lock/unlock the vehicle |

**Lock States:**
- `locked` - `DOOR_LOCKS_STATUS_LOCKED` or `DOOR_LOCKS_STATUS_SAFE_LOCKED`
- `unlocked` - Any other status

### Device Tracker

| Entity | Description |
|--------|-------------|
| `device_tracker.lynk_co_vehicle_tracker` | GPS location tracker with latitude/longitude |

### Sensors Overview

The integration creates 100+ sensors covering all vehicle data. Here are the main categories:

#### Battery & Charging
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_battery` | Main battery charge level (%) |
| `sensor.lynk_co_battery_distance` | Estimated EV range (km) |
| `sensor.lynk_co_charge_state` | Current charging state |
| `sensor.lynk_co_charger_connection_status` | Charger connection status |
| `sensor.lynk_co_time_until_charged` | Minutes until fully charged |

#### Fuel
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_fuel_level` | Fuel level (liters) |
| `sensor.lynk_co_fuel_distance` | Estimated fuel range (km) |
| `sensor.lynk_co_fuel_level_status` | Fuel level status |
| `sensor.lynk_co_fuel_avg_consumption` | Average fuel consumption |

#### Climate
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_interior_temperature` | Cabin temperature (°C) |
| `sensor.lynk_co_exterior_temperature` | Outside temperature (°C) |

#### Location
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_address` | Human-readable address |
| `sensor.lynk_co_address_raw` | Full address components |
| `sensor.lynk_co_latitude` | GPS latitude |
| `sensor.lynk_co_longitude` | GPS longitude |
| `sensor.lynk_co_altitude` | Current altitude |

#### Vehicle Status
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_odometer` | Total distance (km) |
| `sensor.lynk_co_speed` | Current speed |
| `sensor.lynk_co_door_lock_status` | Overall lock status |

#### 12V Battery
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_12v_battery` | 12V battery status |
| `sensor.lynk_co_12v_battery_voltage` | 12V battery voltage |
| `sensor.lynk_co_12v_battery_health` | 12V battery health |

#### Maintenance
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_days_to_service` | Days until service |
| `sensor.lynk_co_distance_to_service` | Distance until service (km) |
| `sensor.lynk_co_service_warning_status` | Service warning indicator |

#### Doors & Windows
Individual status sensors for each door, window, trunk, hood, and tank flap.

#### Tyres
| Entity | Description |
|--------|-------------|
| `sensor.lynk_co_driver_front_tyre_pressure` | Front left tyre pressure |
| `sensor.lynk_co_driver_rear_tyre_pressure` | Rear left tyre pressure |
| `sensor.lynk_co_passenger_front_tyre_pressure` | Front right tyre pressure |
| `sensor.lynk_co_passenger_rear_tyre_pressure` | Rear right tyre pressure |

For a complete list of all entities, see [entities.md](entities.md).

---

## Sensor State Values

### Charger Connection Status
| Value | Meaning |
|-------|---------|
| `CHARGER_CONNECTION_CONNECTED_WITH_POWER` | Charger connected and providing power |
| `CHARGER_CONNECTION_DISCONNECTED` | No charger connected |
| `CHARGER_CONNECTION_CONNECTED_NO_POWER` | Charger connected but not charging |

### Charge State
| Value | Meaning |
|-------|---------|
| `CHARGE_STATE_CHARGING` | Actively charging |
| `CHARGE_STATE_FULLY_CHARGED` | Charge complete |
| `CHARGE_STATE_NOT_CHARGING` | Not currently charging |

### Door Lock Status
| Value | Meaning |
|-------|---------|
| `DOOR_LOCKS_STATUS_LOCKED` | All doors locked |
| `DOOR_LOCKS_STATUS_SAFE_LOCKED` | All doors securely locked |
| `DOOR_LOCKS_STATUS_UNLOCKED` | Doors unlocked |

### Engine Status
| Value | Meaning |
|-------|---------|
| `ENGINE_RUNNING` | Engine/EV system running |
| `ENGINE_OFF` | Engine/EV system off |
| `NO_ENGINE_INFO` | Status unavailable |

### Fuel Level Status
| Value | Meaning |
|-------|---------|
| `FUEL_LEVEL_STATUS_OK` | Fuel level normal |
| `FUEL_LEVEL_STATUS_LOW` | Low fuel warning |
| `FUEL_LEVEL_STATUS_VERY_LOW` | Very low fuel |

### Window/Door Position Status
| Value | Meaning |
|-------|---------|
| `WINDOW_STATUS_CLOSED` | Window fully closed |
| `WINDOW_STATUS_OPEN` | Window open |
| `WINDOW_STATUS_AJAR` | Window partially open |
| `DOOR_OPEN_STATUS_CLOSED` | Door closed |
| `DOOR_OPEN_STATUS_OPEN` | Door open |

---

## Troubleshooting

### Authentication Issues

**Problem**: Login link doesn't work or authentication fails

**Solutions**:
1. Make sure you're using the complete redirect URL (starts with `msauth.com.lynkco.prod.lynkco-app://auth?code=`)
2. Use browser Developer Tools → Network tab → filter for `msauth://prod.lynkco.app.crisp.prod/`
3. The URL is only valid for a short time - complete the process promptly
4. Clear browser cookies and try again if the login page seems stuck

### Sensors Show "Unavailable"

**Problem**: Sensors appear as unavailable after setup

**Solutions**:
1. Wait a few minutes - the first data fetch happens automatically on setup
2. Call `lynkco.force_update_data` service to trigger a manual refresh
3. Check Home Assistant logs for any API errors
4. Verify your vehicle has cellular connectivity

### Token Expiration

**Problem**: Integration stops working after some time

**Solutions**:
1. The integration automatically refreshes tokens
2. If automatic refresh fails, you'll need to reconfigure the integration
3. Go to **Integrations** → **Lynk & Co** → **Delete** and set up again

### Smart Polling Not Working

**Problem**: Data doesn't update during expected times

**Solutions**:
1. Check if current time is within your configured active hours
2. Remember that active hours have a random 0-20 minute offset
3. Use `force_update_data` for immediate updates regardless of schedule
4. Verify smart polling is enabled in options

### Connection Issues

**Problem**: API calls fail or timeout

**Solutions**:
1. Verify your vehicle is in an area with cellular reception
2. Check that your Lynk & Co account is active (try the official app)
3. The Lynk & Co API may have temporary outages - wait and retry

---

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- Original integration by [@TobiasLaross](https://github.com/TobiasLaross)
- Authentication fix inspired by [Donkie's fork](https://github.com/Donkie/Hass-Lynk-Co)
- Thanks to all contributors and the Home Assistant community

---

**Repository**: [https://github.com/johnneerdael/Lynk-Co-HA](https://github.com/johnneerdael/Lynk-Co-HA)
