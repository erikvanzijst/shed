#!/usr/bin/env python3
import json
import os
import sys
import time
from threading import Thread

import pigpio
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

TACH_PIN = 27
PWM_PIN = 18            # Hardware PWM pin
PWM_FREQUENCY = 25000   # 25 kHz as per the Intel spec
PULSES_PER_REV = 2
PUSH_INTERVAL = 5

MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.0.110")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
CLIENT_ID = "shed-fan"

BASE_TOPIC = "homeassistant/sensor/shed"
RPM_STATE = "home/shed/fan/rpm"

rpm_config = {
    "name": "Shed Fan RPM",
    "state_topic": RPM_STATE,
    "unit_of_measurement": "RPM",
    "unique_id": "shed_fan_rpm",
    "device": {
        "identifiers": ["shed-fan"],
        "name": "Shed Fan",
        "manufacturer": "De Prutser",
        "model": "Raspberry Pi 2B + PWM Fan",
    }
}

rpm = 0
last_tick = None


def tach_callback(gpio, level, tick):
    global last_tick, rpm

    if level == 0:
        if last_tick is not None:
            dt = pigpio.tickDiff(last_tick, tick)  # microseconds
            rpm = 60_000_000 / (dt * PULSES_PER_REV)
        last_tick = tick


def get_duty_cycle():
    try:
        duty = int(input("Duty cycle: ").strip())
        if not (0 <= duty <= 100):
            print("Duty must be between 0 and 100", file=sys.stderr)
            return get_duty_cycle()
        return duty
    except ValueError:
        print("Invalid duty cycle", file=sys.stderr)
        return get_duty_cycle()


def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.publish(f"{BASE_TOPIC}/fan/config", json.dumps(rpm_config), retain=True)


def main():
    ha = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID)

    ha.on_connect = on_connect
    ha.username_pw_set(
        os.environ.get("MQTT_USERNAME", "mqtt"),
        os.environ.get("MQTT_PASSWORD", "mqtt"),
    )
    ha.connect(host=MQTT_HOST, port=MQTT_PORT)
    ha.loop_start()

    pi = pigpio.pi()
    if not pi.connected:
        print("Failed to connect to pigpio daemon", file=sys.stderr)
        exit(1)

    try:
        pi.set_mode(TACH_PIN, pigpio.INPUT)
        pi.set_pull_up_down(TACH_PIN, pigpio.PUD_UP)
        pi.set_glitch_filter(TACH_PIN, 1000)  # ignore pulses < 1ms
        cb = pi.callback(TACH_PIN, pigpio.FALLING_EDGE, tach_callback)

        def report_rpm():
            while True:
                print(f"RPM: {rpm:.0f}")
                ha.publish(RPM_STATE, round(rpm), retain=True)
                time.sleep(PUSH_INTERVAL)
        Thread(target=report_rpm, daemon=True).start()

        try:
            while True:
                pct = get_duty_cycle()
                # Convert percentage to range 0–1,000,000 (pigpio hardware PWM scale)
                duty_cycle = int((100 - pct) * 10000)

                pi.hardware_PWM(PWM_PIN, PWM_FREQUENCY, duty_cycle)
                print(f"Set PWM to {pct}% at {PWM_FREQUENCY} Hz")

        finally:
            cb.cancel()
    finally:
        pi.stop()


if __name__ == "__main__":
    main()
