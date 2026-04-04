import cv2
import numpy as np
from picamera2 import Picamera2
from turntable import Turntable
import os
from datetime import datetime

def save_image(frame):
    # 1. Create folder if it doesn't exist
    if not os.path.exists("captures_good"):
        os.makedirs("captures_good")
    
    # 2. Find the next available index
    # List all files, filter for those starting with 'image_' and ending in '.jpg'
    existing_files = [f for f in os.listdir("captures_good") if f.startswith("image_") and f.endswith(".jpg")]
    
    if not existing_files:
        next_index = 0
    else:
        # Extract numbers from filenames like 'image_5.jpg' -> 5
        indices = []
        for f in existing_files:
            try:
                # Split by '_' and '.' to get the middle number
                num = int(f.split('_')[1].split('.')[0])
                indices.append(num)
            except (IndexError, ValueError):
                continue
        next_index = max(indices) + 1 if indices else 0

    # 3. Save with the new index
    filename = f"captures_good/image_{next_index}.jpg"
    cv2.imwrite(filename, frame)
    print(f"--- Image saved to {filename} ---")

def main():
    # 1. Initialize Camera
    picam2 = Picamera2()
    turntable = Turntable()

    # 2. Configure for a standard resolution (easy on the VNC bandwidth)
    config = picam2.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
    picam2.configure(config)

    # 3. Start the camera
    print("Starting camera... Press 'q' in the window to exit.")
    picam2.start()
    num_imgs = 0

    try:
        while True:
            # Capture a frame as a numpy array
            frame = picam2.capture_array()
            # Picamera2 outputs RGB, OpenCV expects BGR
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            save_image(frame_bgr)
            num_imgs = num_imgs + 1
            if turntable.step(speed=0.001): break

        while True:
            if turntable.step(speed=0.001): break
    except KeyboardInterrupt:
        print("\nStopping scanner...")
    finally:
        turntable.cleanup()
        # 5. Clean up
        picam2.stop()
        print("Camera stopped and turntable cleaned up")
        print(f"number of images: {num_imgs}")

if __name__ == "__main__":
    main()