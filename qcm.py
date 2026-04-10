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

        self.latest_frame = None
        self.close_shutter()

    def _camera_config(self):
        config = self.camera.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
        self.camera.configure(config)
        self.camera.post_callback = self._frame_callback
        self.camera.start()

    def _frame_callback(self, request):
        frame = request.make_array("main")
        self.latest_frame = frame

    def evaluate_birdie(self):
        print("Evaluating Birdie")
        while True:
            # Capture a frame as a numpy array
            print("Capturing Frame")
            # frame = self.camera.capture_array()
            frame = self.latest_frame
            if frame is None:
                continue
            # Picamera2 outputs RGB, OpenCV expects BGR
            print("Submitting to queue")
            cropped = frame[100:300, 270:350]
            self.nestSight.submit_image(cropped, self.frame_idx)
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

    def turntableHome(self):
        self.turntable.returnHome()

    def cleanup(self):
        self.nestSight.stop()
        # self.nestSight.shutdown_pool()
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
        os._exit(0)

# --- Execution ---
if __name__ == "__main__":
    main()


