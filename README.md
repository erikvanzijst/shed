# Shed

Home Assistant scripts running on a Raspberry Pi 2 in the garden shed.

## Scripts

- **`sensor.py`** — Reads temperature and humidity from an AHT20 sensor (I2C) and publishes values to Home Assistant via MQTT.
- **`lights.py`** — Controls a relay connected to GPIO 17, exposing it as a switch in Home Assistant via MQTT discovery.

Both scripts register themselves with Home Assistant's MQTT discovery protocol, so they appear automatically once the broker is reachable.

## Configuration

Create a `.env` file in this directory:

```env
MQTT_HOST=ha.local
MQTT_PORT=1883
MQTT_USERNAME=username
MQTT_PASSWORD=password
```

`.env` is git-ignored — the scripts fall back to sensible defaults if a value is missing, so you only need to override what differs from those defaults.

## Install on RPi

1. Copy this project into a directory on the Pi (e.g. via `git clone` or `rsync`).
2. Run:

```bash
./install.sh
```

This installs dependencies with `uv sync`, generates systemd user services from templates, enables them, and starts monitoring their status. Both services are set to auto-start on boot.

To view logs:

```bash
journalctl --user -u lights.service -f
journalctl --user -u dht-sensor.service -f
```
