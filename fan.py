#!/usr/bin/env python3
import json
import os
import sys
import time
from functools import partial
from threading import Thread

import pigpio
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

TACH_PIN = 27
PWM_PIN = 18            # Hardware PWM pin
PWM_FREQUENCY = 25000   # 25 kHz as per the Intel spec
PULSES_PER_REV = 2
BOOT_DUTY_PCT = 30
PUSH_INTERVAL = 1

MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.0.110")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
CLIENT_ID = "shed-fan"

RPM_DISCOVERY  = "homeassistant/sensor/shed/fan/config"
DUTY_DISCOVERY = "homeassistant/number/shed/fan_duty/config"

RPM_STATE  = "home/shed/fan/rpm"
DUTY_STATE = "home/shed/fan/duty"
DUTY_CMD   = "home/shed/fan/set"

_DEVICE = {
    "identifiers": ["shed-fan"],
    "name": "Shed Fan",
    "manufacturer": "De Prutser",
    "model": "Raspberry Pi 2B + PWM Fan",
}

rpm_config = {
    "name": "Shed Fan RPM",
    "state_topic": RPM_STATE,
    "unit_of_measurement": "RPM",
    "unique_id": "shed_fan_rpm",
    "device": _DEVICE,
}

duty_config = {
    "name": "Shed Fan Duty Cycle",
    "command_topic": DUTY_CMD,
    "state_topic": DUTY_STATE,
    "min": 0,
    "max": 100,
    "step": 1,
    "unit_of_measurement": "%",
    "unique_id": "shed_fan_duty",
    "device": _DEVICE,
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


def set_duty(pi, client, pct):
    # Invert percentage because PWM drives an N-FET that acts as an inverter
    pi.hardware_PWM(PWM_PIN, PWM_FREQUENCY, int((100 - pct) * 10000))
    client.publish(DUTY_STATE, pct, retain=True)

    print(f"Set PWM to {pct}% at {PWM_FREQUENCY} Hz")


def on_connect(pi, client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.publish(RPM_DISCOVERY,  json.dumps(rpm_config),  retain=True)
    client.publish(DUTY_DISCOVERY, json.dumps(duty_config), retain=True)
    client.subscribe(DUTY_CMD)
    set_duty(pi, client, BOOT_DUTY_PCT)


def on_message(pi: pigpio.pi, client, userdata, msg):
    try:
        pct = int(msg.payload.decode().strip())
    except ValueError:
        print(f"Invalid duty cycle payload: {msg.payload!r}", file=sys.stderr)
        return
    if not (0 <= pct <= 100):
        print(f"Duty cycle out of range: {pct}", file=sys.stderr)
        return

    set_duty(pi, client, pct)


def main():
    pi = pigpio.pi()
    if not pi.connected:
        print("Failed to connect to pigpio daemon", file=sys.stderr)
        exit(1)

    try:
        pi.set_mode(TACH_PIN, pigpio.INPUT)
        pi.set_pull_up_down(TACH_PIN, pigpio.PUD_UP)
        pi.set_glitch_filter(TACH_PIN, 1000)  # ignore pulses < 1ms
        cb = pi.callback(TACH_PIN, pigpio.FALLING_EDGE, tach_callback)

        ha = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=CLIENT_ID)
        ha.on_connect = partial(on_connect, pi)
        ha.on_message = partial(on_message, pi)
        ha.username_pw_set(
            os.environ.get("MQTT_USERNAME", "mqtt"),
            os.environ.get("MQTT_PASSWORD", "mqtt"),
        )
        ha.connect(host=MQTT_HOST, port=MQTT_PORT)

        def report_rpm():
            while True:
                print(f"RPM: {rpm:.0f}")
                ha.publish(RPM_STATE, round(rpm), retain=True)
                time.sleep(PUSH_INTERVAL)
        Thread(target=report_rpm, daemon=True).start()

        try:
            ha.loop_forever()
        finally:
            cb.cancel()
    finally:
        pi.hardware_PWM(PWM_PIN, PWM_FREQUENCY, 0)
        pi.stop()


if __name__ == "__main__":
    main()
