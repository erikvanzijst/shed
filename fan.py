#!/usr/bin/env python3
import sys
import time

import pigpio

TACH_PIN = 27
PWM_PIN = 18            # Hardware PWM pin
PWM_FREQUENCY = 25000   # 25 kHz as per the Intel spec
PULSES_PER_REV = 2

rpm = 0
last_tick = None
last_print_ts = time.time()

def tach_callback(gpio, level, tick):
    global last_tick, last_print_ts, rpm

    if level == 0:
        if last_tick is not None:
            dt = pigpio.tickDiff(last_tick, tick)  # microseconds
            rpm = 60_000_000 / (dt * PULSES_PER_REV)
        last_tick = tick

    if time.time() - last_print_ts > 1:
        print(f"RPM: {rpm:.0f}")
        last_print_ts = time.time()


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
