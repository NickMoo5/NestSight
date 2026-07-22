import time
from enum import Enum
import hardware_defines as hw
from stepper_motor_driver import StepperDriver, Direction

class ShutterState(Enum):
    OPEN = 1
    CLOSED = 0

class Shutter:

    SPEED = 0.0003

    def __init__(self, steps_to_move=630):
        # Initialize the shared driver using our specific Hardware Defines
        self.motor = StepperDriver(
            step_pin=hw.M1_STEP,
            dir_pin=hw.M1_DIR,
            en_pin=hw.M1_EN,
            ms_pins=(hw.M1_MS1, hw.M1_MS2, hw.M1_MS3)
        )
        
        # Configure for 1/4 stepping as previously requested
        self.motor.set_microstepping(0, 1, 0)
        
        self.steps_to_move = steps_to_move
        self.state = ShutterState.CLOSED
        print(f"Shutter Online. Assumed state: {self.state.name}")

    def open(self, speed=SPEED):
        if self.state == ShutterState.OPEN:
            print("Already open.")
            return
        
        print("Opening Shutter...")
        # We use Direction.CW or CCW from the driver class
        self.motor.enable()
        self.motor.move(self.steps_to_move, Direction.CCW, speed)
        self.motor.disable()
        self.state = ShutterState.OPEN

    def close(self, speed=SPEED):
        if self.state == ShutterState.CLOSED:
            print("Already closed.")
            return
            
        print("Closing Shutter...")
        self.motor.enable()
        self.motor.move(self.steps_to_move, Direction.CW, speed)
        self.motor.disable()
        self.state = ShutterState.CLOSED

    def cleanup(self):
        # self.close()
        self.motor.cleanup()
        print(f"Last known state: {self.state.name}")

def main():
    shutter = Shutter()
    try:
        shutter.open()
        time.sleep(1)
        shutter.close()
    finally:
        shutter.cleanup()

# --- Execution ---
if __name__ == "__main__":
    main()


