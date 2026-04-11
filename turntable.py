import hardware_defines as hw
from stepper_motor_driver import StepperDriver, Direction
import json
import os
import time

FULL_REV = 360

class Turntable:

    def __init__(self, gear_ratio=3.39, config_file="turntable_state.json"):
        # Initialize Motor 2 from hardware_defines
        self.motor = StepperDriver(
            step_pin=hw.M2_STEP,
            dir_pin=hw.M2_DIR,
            en_pin=hw.M2_EN,
            ms_pins=(hw.M2_MS1, hw.M2_MS2, hw.M2_MS3)
        )
        
        # Set to 1/4 stepping (MS1:0, MS2:1, MS3:0)
        self.motor.set_microstepping(0, 1, 0)
        
        # Gear and Step Logic
        self.gear_ratio = gear_ratio
        # 800 (motor steps at 1/4) * 3.4 (gears) = 2720 total pulses for 360° output
        self.total_pulses_per_rev = int(800 * gear_ratio) 
        
        # 15 pulses = ~1.985 degrees at the turntable surface
        self.pulses_per_move = 15
        self.degrees_per_move = 2 
        
        self.config_file = config_file
        self.data = self._load_data()
        print(f"Turntable System Online. Current Position: {self.data['pos']} Direction: {self.data["dir"]}")

    def enable(self):
        self.motor.enable()

    def disable(self):
        self.motor.disable()

    def _load_data(self):
        """Loads position and direction from turntable_state.json"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except: 
                pass
        return {"pos": 0, "dir": "CW"}

    def _save_data(self):
        """Saves position and direction to turntable_state.json"""
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f)

    def step(self, speed=0.001):
        change_direction = False
        """Rotates the turntable ~2 degrees and auto-reverses at 360°."""
        current_dir_enum = Direction.CCW if self.data["dir"] == "CCW" else Direction.CW          
        # if current_dir_enum == Direction.CCW:       # reverse direction due to gearing
        #     reverse_dir = Direction.CW
        # elif current_dir_enum == Direction.CW:
        #     reverse_dir = Direction.CCW

        # Move the 15-pulse burst (Quarter Stepping)
        self.motor.move(self.pulses_per_move, current_dir_enum, speed)
        
        # Update tracking based on direction
        if self.data["dir"] == "CCW":
            self.data["pos"] += self.degrees_per_move
        else:
            self.data["pos"] -= self.degrees_per_move

        # Auto-Reverse Logic
        if self.data["pos"] >= FULL_REV:
            self.data["dir"] = "CW"
            print("--- Turntable reached 360° limit: Reversing to CW ---")
            change_direction = True
        elif self.data["pos"] <= 0:
            self.data["dir"] = "CCW"
            print("--- Turntable reached 0° limit: Reversing to CCW ---")
            change_direction = True

        self._save_data()

        return change_direction

    def returnHome(self):
        while self.data["pos"] != 0: 
           self.step(speed=0.001)

    def cleanup(self):
        """Disables motor and closes GPIO chip"""
        print("Cleaning up Turntable resources...")
        self.returnHome()
        self.motor.cleanup()

def main():
    # Initialize the turntable
    # If your motor is 200 steps/rev and you use 1/4 stepping, total steps = 800
    turntable = Turntable()

    print("Starting scan loop. Press Ctrl+C to stop.")
    try:
        # turntable.cleanup()
        while True:
            if turntable.step(speed=0.001): break

    #     # for i in range(10): 
    #     #     turntable.step(speed=0.003)
    #     #     time.sleep(0.2)
        
        
        
    except KeyboardInterrupt:
        print("\nStopping scanner...")
    finally:
        turntable.cleanup()

if __name__ == "__main__":
    main()