import time
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory

# --- CONFIGURATION ---
# Miuzei servos typically operate on a pulse width of 500us (0.5ms) to 2500us (2.5ms).
# Standard gpiozero defaults might restrict the range, so we define them precisely.
MIN_PW = 0.5 / 1000  # 500 microseconds
MAX_PW = 2.5 / 1000  # 2500 microseconds
SERVO_PIN = 18       # GPIO pin number (Broadcom/BCM numbering)

# Optional: Using pigpio factory eliminates hardware PWM jitter.
# To use this, run 'sudo pigpiod' in your terminal first.
try:
    factory = PiGPIOFactory()
    servo = Servo(SERVO_PIN, min_pulse_width=MIN_PW, max_pulse_width=MAX_PW, pin_factory=factory)
    print("Using pigpio factory for jitter-free control.")
except:
    servo = Servo(SERVO_PIN, min_pulse_width=MIN_PW, max_pulse_width=MAX_PW)
    print("Using default GPIO pin factory.")

def move_servo():
    try:
        print("\n--- Starting Servo Demonstration ---")
        
        while True:
            servo.max()
            time.sleep(1)
            servo.min()
            time.sleep(1)
        
        '''
        # 1. Move to Center (0)
        print("Moving to Center...")
        servo.mid()
        time.sleep(1.5)
        
        # 2. Move to Minimum (-1 represents 0 degrees)
        print("Moving to Minimum Position (0�)...")
        servo.min()
        time.sleep(1.5)
        
        # 3. Move to Maximum (1 represents 180 or 270 degrees depending on your model)
        print("Moving to Maximum Position...")
        servo.max()
        time.sleep(1.5)
        
        # 4. Continuous Smooth Sweep
        print("\nStarting continuous sweep. Press Ctrl+C to stop.")
        while True:
            # Sweep from min to max
            for value in range(-100, 101, 2):
                servo.value = value / 100.0
                time.sleep(0.01)
            
            # Sweep from max to min
            for value in range(100, -101, -2):
                servo.value = value / 100.0
                time.sleep(0.01)
        '''
                 
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")
    finally:
        # Detach the servo to stop it from holding position/drawing power
        servo.detach()
        print("Servo detached safely.")

if __name__ == "__main__":
    move_servo()