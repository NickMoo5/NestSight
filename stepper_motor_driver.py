import lgpio
import time
from enum import Enum

class Direction(Enum):
    CW = 1
    CCW = 0

class StepperDriver:
    def __init__(self, step_pin, dir_pin, en_pin, ms_pins):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.en_pin = en_pin
        self.ms_pins = ms_pins # (MS1, MS2, MS3)
        
        self.h = lgpio.gpiochip_open(0)
        for pin in [step_pin, dir_pin, en_pin] + list(ms_pins):
            lgpio.gpio_claim_output(self.h, pin)
        
        self.enable()

    def enable(self): lgpio.gpio_write(self.h, self.en_pin, 0)
    def disable(self): lgpio.gpio_write(self.h, self.en_pin, 1)

    def set_microstepping(self, m1, m2, m3):
        lgpio.gpio_write(self.h, self.ms_pins[0], m1)
        lgpio.gpio_write(self.h, self.ms_pins[1], m2)
        lgpio.gpio_write(self.h, self.ms_pins[2], m3)

    def move(self, steps, direction, speed=0.0005):
        lgpio.gpio_write(self.h, self.dir_pin, direction.value)
        for _ in range(steps):
            lgpio.gpio_write(self.h, self.step_pin, 1)
            time.sleep(speed)
            lgpio.gpio_write(self.h, self.step_pin, 0)
            time.sleep(speed)

    def cleanup(self):
        self.disable()
        lgpio.gpiochip_close(self.h)


def main():
    # --- Main Logic ---

    # Optional Keyboard Import
    try:
        import keyboard
        use_keyboard = True
    except ImportError:
        print("keyboard module not found, falling back to Enter key.")
        use_keyboard = False

    # Initialize Motors
    motor1 = StepperDriver(step_pin=27, dir_pin=22, en_pin=17, ms1=10, ms2=9, ms3=11)
    motor2 = StepperDriver(step_pin=20, dir_pin=21, en_pin=7, ms1=1, ms2=12, ms3=16)

    print("Press SPACE (or Enter) to trigger motors, CTRL+C to exit.")

    try:
        while True:
            trigger = False
            if use_keyboard:
                if keyboard.is_pressed('space'):
                    trigger = True
                    print("Triggered via SPACE!")
            else:
                input("Press Enter to trigger motors...")
                trigger = True

            if trigger:
                motor1.enable()
                motor2.enable()
                # Motor 1: Move Right
                motor1.move(500, Direction.RIGHT, speed=0.0005)
                motor2.move(100, Direction.RIGHT, speed=0.001)

                time.sleep(2)
            #Motor 1: Move Left
                motor1.move(500, Direction.LEFT, speed=0.0005)
                motor2.move(100, Direction.LEFT, speed=0.001)

                # motor1.single_step(Direction.RIGHT)
                # time.sleep(2)
                # motor1.single_step(Direction.LEFT)

                # Debounce for keyboard
                if use_keyboard:
                    while keyboard.is_pressed('space'):
                        time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        motor1.cleanup()
        motor2.cleanup()
        print("Motors disabled, lgpio handles closed. Cleanup complete.")

if __name__ == "__main__":
    main()