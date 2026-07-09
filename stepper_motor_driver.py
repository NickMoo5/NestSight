import time
import lgpio
from enum import Enum


class Direction(Enum):
    CW = 1
    CCW = 0


class StepperDriver:
    """
    Reusable stepper motor driver for STEP/DIR/EN style drivers.

    Assumptions:
    - enable pin is active-low: 0 = enabled, 1 = disabled
    - step pulse occurs on rising edge
    """

    def __init__(self, step_pin, dir_pin, en_pin=None, ms_pins=None):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.en_pin = en_pin
        self.ms_pins = tuple(ms_pins or ())

        self.h = None
        self.claimed = []

        try:
            self.h = lgpio.gpiochip_open(0)

            # Claim outputs with safe initial levels
            self._claim_output(self.step_pin, 0, "step_pin")
            self._claim_output(self.dir_pin, 0, "dir_pin")

            if self.en_pin is not None:
                # default disabled for safety
                self._claim_output(self.en_pin, 1, "en_pin")

            for i, pin in enumerate(self.ms_pins, start=1):
                self._claim_output(pin, 0, f"ms_pins[{i}]")

        except Exception:
            self.cleanup()
            raise

    def _claim_output(self, pin, level, name="gpio"):
        try:
            lgpio.gpio_claim_output(self.h, pin, level)
            self.claimed.append(pin)
        except Exception as e:
            raise RuntimeError(f"Failed to claim {name} (GPIO {pin}): {e}") from e

    def enable(self):
        if self.en_pin is not None:
            lgpio.gpio_write(self.h, self.en_pin, 0)

    def disable(self):
        if self.en_pin is not None:
            lgpio.gpio_write(self.h, self.en_pin, 1)

    def set_microstepping(self, m1, m2, m3):
        if len(self.ms_pins) != 3:
            raise ValueError("set_microstepping requires exactly 3 microstep pins")
        lgpio.gpio_write(self.h, self.ms_pins[0], int(bool(m1)))
        lgpio.gpio_write(self.h, self.ms_pins[1], int(bool(m2)))
        lgpio.gpio_write(self.h, self.ms_pins[2], int(bool(m3)))

    def step(self, direction, pulse_width=0.0005):
        lgpio.gpio_write(self.h, self.dir_pin, direction.value)
        lgpio.gpio_write(self.h, self.step_pin, 1)
        time.sleep(pulse_width)
        lgpio.gpio_write(self.h, self.step_pin, 0)
        time.sleep(pulse_width)

    def move(self, steps, direction, pulse_width=0.0005):
        lgpio.gpio_write(self.h, self.dir_pin, direction.value)
        for _ in range(steps):
            lgpio.gpio_write(self.h, self.step_pin, 1)
            time.sleep(pulse_width)
            lgpio.gpio_write(self.h, self.step_pin, 0)
            time.sleep(pulse_width)

    def cleanup(self):
        if self.h is None:
            return

        try:
            # put driver in safe state first
            if self.en_pin is not None:
                try:
                    self.disable()
                except Exception:
                    pass

            for pin in reversed(self.claimed):
                try:
                    lgpio.gpio_free(self.h, pin)
                except Exception:
                    pass
            self.claimed.clear()

        finally:
            try:
                lgpio.gpiochip_close(self.h)
            except Exception:
                pass
            self.h = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()