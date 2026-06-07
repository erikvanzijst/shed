import json
import os
import time

import py_AHTx0
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

sensor = py_AHTx0.AHTx0(1, 0x38)
sensor.calibrate()

MQTT_BROKER = os.environ.get("MQTT_HOST", "192.168.0.110")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

CLIENT_ID  = "shed"
BASE_TOPIC = "homeassistant/sensor/shed"
TEMP_STATE = "home/shed/temperature"
HUM_STATE  = "home/shed/humidity"

# -------------------------
# 1. MQTT DISCOVERY CONFIG
# -------------------------

temp_config = {
    "name": "Temperature",
    "state_topic": TEMP_STATE,
    "unit_of_measurement": "°C",
    "device_class": "temperature",
    "unique_id": "shed_dht20_temp",
    "device": {
        "identifiers": ["shed_dht20"],
        "name": "Shed Sensor Node",
        "manufacturer": "DIY",
        "model": "Raspberry Pi + AHT20"
    }
}

hum_config = {
    "name": "Relative humidity",
    "state_topic": HUM_STATE,
    "unit_of_measurement": "%",
    "device_class": "humidity",
    "unique_id": "shed_dht20_hum",
    "device": {
        "identifiers": ["shed_dht20"],
        "name": "Shed Sensor Node",
        "manufacturer": "DIY",
        "model": "Raspberry Pi + AHT20"
    }
}

def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)

def main():
    ha = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID)

    ha.on_connect = on_connect
    ha.username_pw_set(os.environ.get("MQTT_USERNAME", "mqtt"),
                       os.environ.get("MQTT_PASSWORD", "mqtt"))
    ha.connect(host=MQTT_BROKER, port=MQTT_PORT)
    ha.loop_start()

    # Publish config (retained so HA remembers after restart)
    ha.publish(f"{BASE_TOPIC}/temperature/config", json.dumps(temp_config), retain=True)
    ha.publish(f"{BASE_TOPIC}/humidity/config", json.dumps(hum_config), retain=True)

    print("MQTT discovery config sent", flush=True)

    while True:
        temp = round(sensor.temperature, 2)
        hum = round(sensor.relative_humidity, 2)

        print(f"{temp}°C  {hum}%", flush=True)
        ha.publish(TEMP_STATE, temp, retain=True)
        ha.publish(HUM_STATE, hum, retain=True)

        time.sleep(15)

if __name__ == "__main__":
    main()
