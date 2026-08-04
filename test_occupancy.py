"""
Live occupancy-check tester.

Continuously grabs frames from the camera, crops them with the same crop
region as the occupancy reference images, and runs
NestSight.detect_occupancy() so you can watch the diff values and the
EMPTY / BIRDIE / ERROR state in real time while tuning thresholds.

Usage:
    python test_occupancy.py        # Ctrl+C to stop
"""
import time

from picamera2 import Picamera2

from nestSight import NestSight
from reference_images import crop_frame

POLL_INTERVAL = 0.2  # seconds between occupancy checks


def main():
    # NestSight FIRST (same as Qcm): it forks a multiprocessing pool and
    # workers inherit open fds, so create it before the camera is opened.
    nest_sight = NestSight(developer_mode=False)

    camera = Picamera2()
    config = camera.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
    camera.configure(config)
    camera.start()

    print("Live occupancy check running. Ctrl+C to stop.")
    try:
        while True:
            frame = camera.capture_array()
            cropped = crop_frame(frame)
            # detect_occupancy prints: diff_empty, diff_birdie, threshold, state
            nest_sight.detect_occupancy(cropped)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        camera.stop()
        camera.close()
        nest_sight.shutdown_pool()


if __name__ == "__main__":
    main()
