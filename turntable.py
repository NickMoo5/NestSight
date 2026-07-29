import hardware_defines as hw
from stepper_motor_driver import StepperDriver, Direction
import time

FULL_REV = 360
# TURNTABLE_SPEED = 0.00021
TURNTABLE_SPEED = 0.00028 # 1.84 seconds
# TURNTABLE_SPEED = 0.00035
# 0.00025

class Turntable:

    def __init__(self, gear_ratio=3.39):
        # Initialize Motor 1 from hardware_defines
        self.motor = StepperDriver(
            step_pin=hw.M1_STEP,
            dir_pin=hw.M1_DIR,
            en_pin=hw.M1_EN,
            ms_pins=(hw.M1_MS1, hw.M1_MS2, hw.M1_MS3)
        )
        
        # Set to 1/4 stepping (MS1:0, MS2:1, MS3:0)
        #self.motor.set_microstepping(0, 1, 0)
        
        # Gear and Step Logic
        self.gear_ratio = gear_ratio
        # 800 (motor steps at 1/4) * 3.4 (gears) = 2720 total pulses for 360° output
        self.total_pulses_per_rev = int(800 * gear_ratio) 
        
        # 15 pulses = ~1.985 degrees at the turntable surface
        self.pulses_per_move = 15
        self.degrees_per_move = 2 
        
        self.data = {"pos": 0, "dir": "CW"}
        self._ramp_progress = 0  # tracks how many ramped steps taken since the last reset
        print(f"Turntable System Online. Current Position: {self.data['pos']} Direction: {self.data['dir']}")

    def enable(self):
        self.motor.enable()

    def disable(self):
        self.motor.disable()

    def step(self, speed=0.001):
        """Rotates the turntable ~2 degrees CW and wraps back to 0° at 360°."""
        change_direction = False

        # Move the 15-pulse burst (Quarter Stepping), always CW
        self.motor.move(self.pulses_per_move, Direction.CW, speed)

        self.data["pos"] += self.degrees_per_move

        # Wrap back to 0° at the 360° limit
        if self.data["pos"] >= FULL_REV:
            self.data["pos"] = 0
            print("--- Turntable reached 360° limit: Wrapping to 0° ---")
            change_direction = True

        return change_direction

    def stepOne(self, speed=0.001):
        self.motor.move(self.pulses_per_move, Direction.CW, speed)

    def stepRamped(self, final_speed, ramp_steps=5, start_factor=4.0):
        """
        Performs one ~2-degree turntable step, linearly ramping the move
        speed up toward `final_speed` over the first `ramp_steps` calls.
        Ramp progress automatically resets whenever the turntable
        auto-reverses at the 0deg/360deg limit, so each new sweep eases
        back up to speed instead of starting at full speed.

        final_speed : target per-edge delay in seconds once fully ramped
                      up (smaller = faster, same units as step()'s speed).
        ramp_steps  : number of stepRamped() calls over which to ramp
                      from the slow start speed up to final_speed.
        start_factor: how much slower (in delay terms) the first step is,
                      i.e. the ramp begins at final_speed * start_factor.
        """
        start_speed = final_speed * start_factor
        frac = min(self._ramp_progress, ramp_steps) / ramp_steps if ramp_steps > 0 else 1.0
        current_speed = start_speed - (start_speed - final_speed) * frac

        self._ramp_progress += 1

        change_direction = self.step(speed=current_speed)

        if change_direction:
            # Reached 0deg/360deg and reversed - restart the ramp for the new sweep.
            self._ramp_progress = 0

        return change_direction

    def returnHome(self):
        while self.data["pos"] != 0: 
           self.step(speed=0.001)

    def cleanup(self):
        """Disables motor and closes GPIO chip"""
        print("Cleaning up Turntable resources...")
        #self.returnHome()
        self.motor.cleanup()

def main():
    # Initialize the turntable
    # If your motor is 200 steps/rev and you use 1/4 stepping, total steps = 800
    turntable = Turntable()
    turntable.enable()
    print("Starting scan loop. Press Ctrl+C to stop.")
    # for i in range(90):
    #     # turntable.stepRamped(final_speed=0.0004)
    #     turntable.step(speed=0.0006)
    start_time = time.perf_counter()
    while True:
        if turntable.step(speed=TURNTABLE_SPEED): break
    elapsed = time.perf_counter() - start_time
    print(f"Full rotation took {elapsed:.2f} seconds")

    turntable.cleanup()
    # try:
    #     # turntable.cleanup()
    #     # turntable.step(speed=0.003)

    # #     # for i in range(10): 
    # #     #     turntable.step(speed=0.003)
    # #     #     time.sleep(0.2)
        
        
        
    # except KeyboardInterrupt:
    #     print("\nStopping scanner...")
    # finally:
    #     turntable.cleanup()

if __name__ == "__main__":
    main()