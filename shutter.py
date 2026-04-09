import time
import json
import os
from enum import Enum
import hardware_defines as hw
from stepper_motor_driver import StepperDriver, Direction

class ShutterState(Enum):
    OPEN = 1
    CLOSED = 0

class Shutter:

    SPEED = 0.0003

    def __init__(self, steps_to_move=630, config_file="shutter_state.json"):
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
        self.config_file = config_file
        self.state = self._load_state()
        print(f"Shutter Online. Last known state: {self.state.name}")

    def _load_state(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return ShutterState(json.load(f).get("state", 0))
            except: pass
        return ShutterState.CLOSED

    def _save_state(self):
        with open(self.config_file, 'w') as f:
            json.dump({"state": self.state.value}, f)

    def open(self, speed=SPEED):
        if self.state == ShutterState.OPEN:
            print("Already open.")
            return
        
        print("Opening Shutter...")
        # We use Direction.CW or CCW from the driver class
        self.motor.move(self.steps_to_move, Direction.CCW, speed)
        self.state = ShutterState.OPEN
        self._save_state()

    def close(self, speed=SPEED):
        if self.state == ShutterState.CLOSED:
            print("Already closed.")
            return
            
        print("Closing Shutter...")
        self.motor.move(self.steps_to_move, Direction.CW, speed)
        self.state = ShutterState.CLOSED
        self._save_state()

    def cleanup(self):
        self.close()
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


