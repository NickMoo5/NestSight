import time
import json
import os
from enum import Enum
import hardware_defines as hw
from shutter import Shutter
from turntable import TURNTABLE_SPEED, Turntable
from picamera2 import Picamera2
from nestSight import NestSight, BirdieState
import cv2
import capture_images_rotation
from servo_driver_hw import ServoDriverHW
from camera import CROP_Y_START, CROP_Y_END, CROP_X_START, CROP_X_END
from reference_images import (
    CROP_Y_START as OCC_Y_START,
    CROP_Y_END as OCC_Y_END,
    CROP_X_START as OCC_X_START,
    CROP_X_END as OCC_X_END,
)

NO_SHUTTER = True

class Qcm:

    def __init__(self):
        # NestSight FIRST: it forks a multiprocessing pool, and workers
        # inherit all open fds. Creating it before any GPIO is claimed
        # keeps workers from holding /dev/gpiochip* open after a crash.
        self.nestSight = NestSight(developer_mode=True)
        self.turntable = Turntable()
        self.camera = Picamera2()
        self.frame_idx = 0
        self.servo = ServoDriverHW(pin=18)
        self.slide = ServoDriverHW(pin=19)
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
        self.turntable.enable()
        while True:
            # Capture a frame as a numpy array
            # print("Capturing Frame")
            # frame = self.camera.capture_array()
            frame = self.latest_frame
            if frame is None:
                continue
            # Picamera2 outputs RGB, OpenCV expects BGR
            # print("Submitting to queue")
            cropped = frame[CROP_Y_START:CROP_Y_END, CROP_X_START:CROP_X_END]
            # capture_images_rotation.save_image(cropped, "CAPA")
            self.nestSight.submit_image(cropped, self.frame_idx)
            self.frame_idx = self.frame_idx + 1

            if self.turntable.step(speed=TURNTABLE_SPEED): 
                print("Finished rotation")
                self.turntable.disable()
                break

        while not self.nestSight.all_images_processed():
            time.sleep(0.1)
            print(f"Waiting for image processing to complete... {self.nestSight.processed_count()}/{self.frame_idx} processed.")

        self.nestSight.collect_results()
        result = self.nestSight.evaluate()
        # if self.developer_mode:
        #     self.nestSight.generate_pdf_report()

        self.nestSight.reset()
        self.frame_idx = 0
        return result
    
    def check_occupancy(self):
        """Classify the latest frame as EMPTY, BIRDIE, or ERROR."""
        frame = self.latest_frame
        if frame is None:
            return BirdieState.ERROR
        cropped = frame[OCC_Y_START:OCC_Y_END, OCC_X_START:OCC_X_END]
        return self.nestSight.detect_occupancy(cropped)

    def drop(self):
        self.open_shutter()
        time.sleep(0.8)
        self.close_shutter()
        # time.sleep(0.5)
        # self.servo.detach()

    def open_shutter(self):
        # Override driver open(): manually set to max
        self.servo.move_to_value(1.0, False)

    def close_shutter(self):
        # Override driver close(): manually set to min
        self.servo.move_to_value(-0.9, False)

    def open_slide(self):
        self.slide.open()

    def close_slide(self):
        self.slide.close()

    def cleanup(self):
        # Run every step even if one fails, so GPIO always gets released.
        for step in (
            self.nestSight.stop,
            self.nestSight.shutdown_pool,
            self.turntable.cleanup,
            self.servo.cleanup,
            self.slide.cleanup,
            self.camera.stop,
        ):
            try:
                step()
            except Exception as e:
                print(f"[CLEANUP] {step.__qualname__} failed: {e}")

def main():
    qcm = Qcm()
    qcm.developer_mode = True

    try:
        while True:
            state = qcm.check_occupancy()

            if state != BirdieState.BIRDIE:
                print(f"No birdie detected ({state.name}), checking again in 4s...")
                time.sleep(4)
                continue

            print("Birdie detected! Evaluating Birdie")
            result = qcm.evaluate_birdie()
            print(f"VERDICT:    {result}")
            if result != "PASS":
                qcm.open_slide()
            qcm.drop()
            time.sleep(0.5)
            qcm.close_slide()
            time.sleep(0.2)
            # qcm.slide.detach()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        qcm.cleanup()
        os._exit(0)

# --- Execution ---
if __name__ == "__main__":
    main()


