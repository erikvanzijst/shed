#!/usr/bin/env python3
import json
import os
from dotenv import load_dotenv

import pigpio
import paho.mqtt.client as mqtt

load_dotenv()

PIN = 22

MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.0.110")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
CLIENT_ID = "shed-kitt"

DISCOVERY = "homeassistant/switch/shed/kitt/config"

TOPIC_SET = "home/shed/kitt/set"
TOPIC_STATE = "home/shed/kitt/state"
TOPIC_AVAIL = "home/shed/kitt/availability"

switch_config = {
    "name": "KITT",
    "unique_id": "shed_kitt",

    "command_topic": TOPIC_SET,
    "state_topic": TOPIC_STATE,

    "payload_on": "ON",
    "payload_off": "OFF",

    "state_on": "ON",
    "state_off": "OFF",

    "availability_topic": TOPIC_AVAIL,

    "payload_available": "online",
    "payload_not_available": "offline",

    "device": {
        "identifiers": ["shed-kitt"],
        "name": "Knight Rider",
        "manufacturer": "De Prutser",
        "model": "Knight Rider lights",
    }
}


pi = pigpio.pi()
if not pi.connected:
    raise RuntimeError("Cannot connect to pigpiod")
pi.set_mode(PIN, pigpio.OUTPUT)
pi.write(PIN, 1)    # Start with the kitt off

ha = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=CLIENT_ID)

ha.username_pw_set(
    os.environ.get("MQTT_USERNAME", "mqtt"),
    os.environ.get("MQTT_PASSWORD", "mqtt"),
)


def kitt_is_on():
    return pi.read(PIN) == 1

def publish_state():
    ha.publish(
        TOPIC_STATE,
        "ON" if kitt_is_on() else "OFF",
        retain=True
    )

def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)

    ha.publish(DISCOVERY, json.dumps(switch_config), retain=True)

    client.publish(
        TOPIC_AVAIL,
        "online",
        retain=True
    )

    client.subscribe(TOPIC_SET)
    publish_state()

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip().upper()
    print(f"Switching kitt {payload}", flush=True)

    if payload == "ON":
        pi.write(PIN, 1)

    elif payload == "OFF":
        pi.write(PIN, 0)

    publish_state()

ha.will_set(
    TOPIC_AVAIL,
    "offline",
    retain=True
)

ha.on_connect = on_connect
ha.on_message = on_message
ha.connect(host=MQTT_HOST, port=MQTT_PORT)

try:
    ha.loop_forever()

finally:
    pi.write(PIN, 0)
    pi.stop()

