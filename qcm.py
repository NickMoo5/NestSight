import time
import json
import os
from enum import Enum
import lgpio
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

    def __init__(self, developer_mode=False):
        self.developer_mode = developer_mode
        self.nestSight = None
        self.turntable = None
        self.camera = None
        self.servo = None
        self.slide = None
        self._gpio_h = None
        try:
            # NestSight FIRST: it forks a multiprocessing pool, and workers
            # inherit all open fds. Creating it before any GPIO is claimed
            # keeps workers from holding /dev/gpiochip* open after a crash.
            self.nestSight = NestSight(developer_mode=developer_mode)
            self.turntable = Turntable()
            self.camera = Picamera2()
            self.frame_idx = 0
            self.servo = ServoDriverHW(pin=18)
            self.slide = ServoDriverHW(pin=19)
            self._camera_config()
            self.nestSight.start()

            # QCM enable switch (not wired yet if pin is None)
            if hw.QCM_ENABLE_SWITCH is not None:
                self._gpio_h = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_input(self._gpio_h, hw.QCM_ENABLE_SWITCH, lgpio.SET_PULL_UP)

            self.latest_frame = None
            self.close_shutter()
        except BaseException:
            # Construction failed partway (error or Ctrl+C): release whatever
            # was already created so pool workers/GPIO don't get stranded.
            self.cleanup()
            raise

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
        if self.developer_mode:
            self.nestSight.generate_pdf_report()

        self.nestSight.reset()
        self.frame_idx = 0
        return result
    
    def is_enabled(self):
        """Read the QCM enable switch. Always enabled until the switch pin
        is wired up (hw.QCM_ENABLE_SWITCH = None)."""
        if self._gpio_h is None:
            return True
        # Pulled up: switch open = 1 = enabled, closed to GND = 0 = disabled.
        # Flip the comparison if the switch is wired the other way.
        return lgpio.gpio_read(self._gpio_h, hw.QCM_ENABLE_SWITCH) == 1

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

    def run_evaluation(self):
        """Full evaluation sequence: evaluate, sort via slide, and drop.
        Returns the verdict string."""
        result = self.evaluate_birdie()
        print(f"VERDICT:    {result}")
        if result != "PASS":
            self.open_slide()
        else:
            self.close_slide()
            time.sleep(0.5)
        # self.drop()
        self.open_shutter()
        time.sleep(0.8)
        self.close_shutter()
        self.close_slide()
        time.sleep(1)
        self.servo.detach()
        self.slide.detach()
        return result

    def _release_enable_switch(self):
        lgpio.gpio_free(self._gpio_h, hw.QCM_ENABLE_SWITCH)
        lgpio.gpiochip_close(self._gpio_h)

    def cleanup(self):
        # Tolerate partially-constructed state and run every step even if
        # one fails, so pool workers and GPIO always get released.
        steps = []
        if self.nestSight is not None:
            steps += [self.nestSight.stop, self.nestSight.shutdown_pool]
        if self.turntable is not None:
            steps.append(self.turntable.cleanup)
        if self.servo is not None:
            steps.append(self.servo.cleanup)
        if self.slide is not None:
            steps.append(self.slide.cleanup)
        if self.camera is not None:
            steps.append(self.camera.stop)
        if self._gpio_h is not None:
            steps.append(self._release_enable_switch)
        for step in steps:
            try:
                step()
            except Exception as e:
                print(f"[CLEANUP] {step.__qualname__} failed: {e}")

def main():
    qcm = None
    try:
        qcm = Qcm(developer_mode=True)

        while True:
            state = qcm.check_occupancy()

            if not state:
                print("No birdie detected, checking again in 4s...")
                time.sleep(4)
            else:
                break

        print("Birdie detected! Evaluating Birdie")
        qcm.run_evaluation()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        if qcm is not None:
            qcm.cleanup()
        os._exit(0)

# --- Execution ---
if __name__ == "__main__":
    main()


