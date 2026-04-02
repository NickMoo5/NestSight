# motor_driver_lgpio.py
# Must run with sudo

import lgpio
import time

try:
    import keyboard  # pip install keyboard
    use_keyboard = True
except ImportError:
    print("keyboard module not found, falling back to Enter key.")
    use_keyboard = False

# --- Pin definitions (BCM numbering) ---
# Motor 1
DIR1_PIN = 22
STEP1_PIN = 27
ENABLE1_PIN = 17

# Motor 2
DIR2_PIN = 23
STEP2_PIN = 24
ENABLE2_PIN = 25

# --- Open lgpio handle ---
h = lgpio.gpiochip_open(0)

# --- Configure pins as output ---
for pin in [DIR1_PIN, STEP1_PIN, ENABLE1_PIN, DIR2_PIN, STEP2_PIN, ENABLE2_PIN]:
    lgpio.gpio_claim_output(h, pin)

# --- Enable motors ---
lgpio.gpio_write(h, ENABLE1_PIN, 0)  # LOW = enable
lgpio.gpio_write(h, ENABLE2_PIN, 0)

# --- Step function ---
# dir = 1 = right
# dir = 0 = left
def move_steps(step_pin, dir_pin, steps, direction):
    lgpio.gpio_write(h, dir_pin, direction)
    for _ in range(steps):
        lgpio.gpio_write(h, step_pin, 1)
        time.sleep(0.0005)  # 500 �1s
        lgpio.gpio_write(h, step_pin, 0)
        time.sleep(0.0005)

# --- Main loop ---
print("Press SPACE (or Enter) to trigger motors, CTRL+C to exit.")

try:
    while True:
        if use_keyboard and keyboard.is_pressed('space'):
            print("Triggered via SPACE!")

            # Motor 1
            move_steps(STEP1_PIN, DIR1_PIN, 594, 1) # right
            time.sleep(2)
            move_steps(STEP1_PIN, DIR1_PIN, 594, 0) # left

            # Wait for key release
            while keyboard.is_pressed('space'):
                time.sleep(0.1)

        elif not use_keyboard:
            input("Press Enter to trigger motors...")

            move_steps(STEP1_PIN, DIR1_PIN, 594, 1)
            time.sleep(2)
            move_steps(STEP1_PIN, DIR1_PIN, 594, 0)

except KeyboardInterrupt:
    print("Exiting...")

finally:
    # Disable motors
    lgpio.gpio_write(h, ENABLE1_PIN, 1)
    lgpio.gpio_write(h, ENABLE2_PIN, 1)

    # Close handle
    lgpio.gpiochip_close(h)
    print("Motors disabled, handle closed.")