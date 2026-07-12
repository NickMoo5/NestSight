import time
from rpi_hardware_pwm import HardwarePWM


class ServoDriverHW:
    """
    Servo driver using the Pi 5's hardware PWM peripheral (no jitter,
    microsecond-accurate pulses -> much better position accuracy than
    software-timed PWM).

    Requires this overlay in /boot/firmware/config.txt (then reboot):
        dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2

    Pi 5 GPIO -> PWM channel mapping (pwmchip0):
        GPIO 12 -> channel 0
        GPIO 13 -> channel 1
        GPIO 18 -> channel 2
        GPIO 19 -> channel 3

    API mirrors servo_driver.py: open(), close(), move_to_value(), cleanup().
    """

    GPIO_TO_CHANNEL = {12: 0, 13: 1, 18: 2, 19: 3}

    def __init__(
        self,
        pin: int = 18,
        min_pulse_width: float = 0.5 / 1000,   # seconds, maps to value -1.0
        max_pulse_width: float = 2.5 / 1000,   # seconds, maps to value +1.0
        open_value: float = 0.25,  # 100 degrees
        close_value: float = 0.79,  # 165 degrees
        move_delay: float = 1.0,
        frequency: int = 50,
    ):
        if pin not in self.GPIO_TO_CHANNEL:
            raise ValueError(f"Hardware PWM only available on GPIO {list(self.GPIO_TO_CHANNEL)}")

        self.pin = pin
        self.min_pulse_width = min_pulse_width
        self.max_pulse_width = max_pulse_width
        self.open_value = open_value
        self.close_value = close_value
        self.move_delay = move_delay
        self.frequency = frequency
        self._period = 1.0 / frequency

        self._pwm = HardwarePWM(pwm_channel=self.GPIO_TO_CHANNEL[pin], hz=frequency, chip=0)
        self._started = False

    def _value_to_duty(self, value: float) -> float:
        """Map a servo value in [-1, 1] to a duty cycle percentage."""
        pulse = self.min_pulse_width + (value + 1.0) / 2.0 * (
            self.max_pulse_width - self.min_pulse_width
        )
        return pulse / self._period * 100.0

    def move_to_value(self, value: float, settle: bool = True):
        """Move servo to a raw position from -1.0 to 1.0."""
        if not -1.0 <= value <= 1.0:
            raise ValueError("Servo value must be between -1.0 and 1.0")

        duty = self._value_to_duty(value)
        if not self._started:
            self._pwm.start(duty)
            self._started = True
        else:
            self._pwm.change_duty_cycle(duty)

        if settle:
            time.sleep(self.move_delay)

    # Alias to match servo_driver.py
    def set_position(self, value: float):
        self.move_to_value(value, settle=False)

    def open(self):
        """Move servo to open position (100 degrees)."""
        self.move_to_value(self.open_value, settle=False)

    def close(self):
        """Move servo to closed position (165 degrees)."""
        self.move_to_value(self.close_value, settle=False)

    def detach(self):
        """Stop sending pulses so the servo stops holding position."""
        self._pwm.stop()
        self._started = False

    def cleanup(self):
        try:
            self.detach()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()


def main():
    """Test loop alternating between 100deg (open) and 165deg (closed)."""
    driver = ServoDriverHW(pin=19)
    print("Starting hardware-PWM servo test (100deg <-> 165deg). Press Ctrl+C to stop.")

    try:
        while True:
            print("Moving to 100deg (open)...")
            driver.open()
            time.sleep(0.5)

            print("Moving to 165deg (closed)...")
            driver.close()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping servo test.")
    finally:
        driver.cleanup()


if __name__ == "__main__":
    main()
