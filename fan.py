#!/usr/bin/env python3
import json
import os
import sys
import time
from collections import deque
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
PUSH_INTERVAL = 5
DUTY_CYCLE_FILE = "./var/duty_cycle"

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
    "name": "Fan Speed",
    "state_topic": RPM_STATE,
    "unit_of_measurement": "RPM",
    "unique_id": "shed_fan_rpm",
    "device": _DEVICE,
}

duty_config = {
    "name": "Fan Power",
    "command_topic": DUTY_CMD,
    "state_topic": DUTY_STATE,
    "min": 0,
    "max": 100,
    "step": 1,
    "unit_of_measurement": "%",
    "unique_id": "shed_fan_duty",
    "device": _DEVICE,
}

class Tachometer:
    _STALE_THRESHOLD = 2.0  # seconds without a pulse → report 0 RPM

    def __init__(self):
        self._last_pulse = None
        self._pulses = deque(maxlen=1000)

    def callback(self, gpio, level, tick):
        if level == 0:
            self._pulses.append(tick)
            self._last_pulse = time.monotonic()
            # Purge expired pulses:
            while pigpio.tickDiff(self._pulses[0], tick) > 5_000_000:
                self._pulses.popleft()


    @property
    def rpm(self) -> int:
        if (self._last_pulse is None or len(self._pulses) < 2 or
                time.monotonic() - self._last_pulse > self._STALE_THRESHOLD):
            return 0
        else:
            avg_pulse = pigpio.tickDiff(self._pulses[0], self._pulses[-1]) / (len(self._pulses) - 1)
            return round(60_000_000 / (avg_pulse * PULSES_PER_REV))


def get_duty():
    try:
        with open(DUTY_CYCLE_FILE, "r") as f:
            return int(f.read())
    except OSError as e:
        print(f"Failed to read duty cycle file {DUTY_CYCLE_FILE}: {e}", file=sys.stderr)
        return 0


def set_duty(pi, client, pct):
    os.makedirs(os.path.dirname(DUTY_CYCLE_FILE), exist_ok=True)
    with open(DUTY_CYCLE_FILE, "w") as f:
        f.write(str(pct))

    # Invert percentage because PWM drives an N-FET that acts as an inverter
    pi.hardware_PWM(PWM_PIN, PWM_FREQUENCY, int((100 - pct) * 10000))
    client.publish(DUTY_STATE, pct, retain=True)

    print(f"Set PWM to {pct}% at {PWM_FREQUENCY} Hz", flush=True)


def on_connect(pi, client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.publish(RPM_DISCOVERY,  json.dumps(rpm_config),  retain=True)
    client.publish(DUTY_DISCOVERY, json.dumps(duty_config), retain=True)
    client.subscribe(DUTY_CMD)
    set_duty(pi, client, get_duty())


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

        tach = Tachometer()
        cb = pi.callback(TACH_PIN, pigpio.FALLING_EDGE, tach.callback)

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
                print(f"RPM: {tach.rpm}", flush=True)
                ha.publish(RPM_STATE, tach.rpm, retain=True)
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
