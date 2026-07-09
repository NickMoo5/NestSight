import time
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory


class ServoDriver:
    """
    Simple reusable servo driver with open/close actions.

    Assumes:
    - "open"  -> servo max position
    - "close" -> servo min position

    You can invert behavior by swapping open_value and close_value.
    """

    def __init__(
        self,
        pin: int = 18,
        min_pulse_width: float = 0.5 / 1000,
        max_pulse_width: float = 2.5 / 1000,
        open_value: float = 1.0,
        close_value: float = -1.0,
        move_delay: float = 1.0,
        use_pigpio: bool = True,
    ):
        self.pin = pin
        self.open_value = open_value
        self.close_value = close_value
        self.move_delay = move_delay

        self._factory = None
        self._servo = None

        if use_pigpio:
            try:
                self._factory = PiGPIOFactory()
                self._servo = Servo(
                    pin,
                    min_pulse_width=min_pulse_width,
                    max_pulse_width=max_pulse_width,
                    pin_factory=self._factory,
                )
                print("Using pigpio factory for jitter-free control.")
            except Exception:
                self._servo = Servo(
                    pin,
                    min_pulse_width=min_pulse_width,
                    max_pulse_width=max_pulse_width,
                )
                print("pigpio unavailable, using default GPIO factory.")
        else:
            self._servo = Servo(
                pin,
                min_pulse_width=min_pulse_width,
                max_pulse_width=max_pulse_width,
            )
            print("Using default GPIO factory.")

    def open(self):
        """Move servo to open position."""
        self._servo.value = self.open_value
        time.sleep(self.move_delay)

    def close(self):
        """Move servo to closed position."""
        self._servo.value = self.close_value
        time.sleep(self.move_delay)

    def set_position(self, value: float):
        """
        Set raw servo position from -1.0 to 1.0.
        Useful for calibration.
        """
        if not -1.0 <= value <= 1.0:
            raise ValueError("Servo value must be between -1.0 and 1.0")
        self._servo.value = value

    def detach(self):
        """Detach servo so it stops holding position."""
        self._servo.detach()

    def cleanup(self):
        """Safe cleanup helper."""
        try:
            self.detach()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()