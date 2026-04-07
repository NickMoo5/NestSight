import cv2
import numpy as np
from picamera2 import Picamera2

import os
from datetime import datetime

def save_image(frame):
    # Create a 'captures' folder if it doesn't exist
    if not os.path.exists("captures"):
        os.makedirs("captures")
    
    # Generate a filename based on the current time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"captures/image_{timestamp}.jpg"
    
    # Save the frame (Ensure it is in BGR format for OpenCV)
    cv2.imwrite(filename, frame)
    print(f"--- Image saved to {filename} ---")

# 1. Initialize Camera
picam2 = Picamera2()

# 2. Configure for a standard resolution (easy on the VNC bandwidth)
config = picam2.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
picam2.configure(config)

# 3. Start the camera
print("Starting camera... Press 'q' in the window to exit.")
picam2.start()

try:
    while True:
        # Capture a frame as a numpy array
        frame = picam2.capture_array()

        # Picamera2 outputs RGB, OpenCV expects BGR
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = frame_bgr[100:295, 280:340].copy()
        # 4. Show the frame in a window
        cv2.imshow("Raspberry Pi 5 Camera", img)

        key = cv2.waitKey(1) & 0xFF

        if key == 32:
            save_image(frame_bgr)

        # Break loop on 'q' key press
        if key == ord('q'):
            break

finally:
    # 5. Clean up
    picam2.stop()
    cv2.destroyAllWindows()
    print("Camera stopped.")