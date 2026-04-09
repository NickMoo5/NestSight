import time
import json
import os
from enum import Enum
import hardware_defines as hw
from shutter import Shutter
from turntable import Turntable
from picamera2 import Picamera2
from nestSight import NestSight
import cv2

NO_SHUTTER = True

class Qcm:

    def __init__(self):
        self.shutter = Shutter()
        self.turntable = Turntable()
        self.camera = Picamera2()
        self.nestSight = NestSight()
        self.frame_idx = 0
        self._camera_config()
        self.nestSight.start()

        self.close_shutter()

    def _camera_config(self):
        config = self.camera.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
        self.camera.configure(config)
        self.camera.start()

    def evaluate_birdie(self):
        print("Evaluating Birdie")
        while True:
            # Capture a frame as a numpy array
            print("Capturing Frame")
            frame = self.camera.capture_array()
            # Picamera2 outputs RGB, OpenCV expects BGR
            print("Converting Frame")
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            print("Submitting to queue")
            self.nestSight.submit_image(frame_bgr, self.frame_idx)
            self.frame_idx = self.frame_idx + 1

            if self.turntable.step(speed=0.001): 
                print("Finished rotation")
                break

        while not self.nestSight.all_images_processed():
            time.sleep(0.1)

        self.nestSight.collect_results()
        result = self.nestSight.evaluate()

        self.nestSight.reset()
        self.frame_idx = 0
        return result
    
    def drop(self):
        self.shutter.open()
        time.sleep(1)
        self.shutter.close()

    def open_shutter(self):
        self.shutter.open()

    def close_shutter(self):
        self.shutter.close()

    def cleanup(self):
        self.nestSight.stop()
        self.turntable.cleanup()
        self.shutter.cleanup()
        self.camera.stop()

def main():
    qcm = Qcm()

    try:
    
        print("Evaluating Birdie")

        result = qcm.evaluate_birdie()
        print(f"VERDICT:    {result}")
        qcm.drop()
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        qcm.cleanup()

# --- Execution ---
if __name__ == "__main__":
    main()


