"""
Reference image tool for QCM occupancy detection.

Generates/updates the cropped reference images used by
NestSight.detect_occupancy():
    reference_images/ref_empty.png
    reference_images/ref_birdie.png

Usage:
    # Capture from the camera (SPACE = save, q = quit without saving):
    python reference_images.py capture empty
    python reference_images.py capture birdie

    # Crop an existing image file and save it as a reference:
    python reference_images.py crop empty  path/to/full_image.png
    python reference_images.py crop birdie path/to/full_image.png

Crop region is defined by this file's own CROP_* values (independent of
camera.py) - make sure frames passed to detect_occupancy() use the same crop.
"""
import argparse
import os

import cv2

from nestSight import REFERENCE_DIR, REF_EMPTY_PATH, REF_BIRDIE_PATH

# --- Crop region for occupancy reference images (placeholders, tune these) ---
CROP_Y_START = 50
CROP_Y_END   = 480
CROP_X_START = 210
CROP_X_END   = 490

REF_PATHS = {
    "empty": REF_EMPTY_PATH,
    "birdie": REF_BIRDIE_PATH,
}


def crop_frame(frame):
    return frame[CROP_Y_START:CROP_Y_END, CROP_X_START:CROP_X_END].copy()


def save_reference(frame, ref_type):
    """Crop a full frame and save it as the given reference image."""
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    path = REF_PATHS[ref_type]
    cv2.imwrite(path, crop_frame(frame))
    print(f"--- Saved {ref_type} reference to {path} ---")


def crop_existing(ref_type, image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    save_reference(img, ref_type)


def capture_reference(ref_type):
    from picamera2 import Picamera2

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)})
    picam2.configure(config)

    print(f"Capturing '{ref_type}' reference. SPACE = save, q = quit.")
    picam2.start()

    try:
        while True:
            frame = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            cv2.imshow(f"Reference capture ({ref_type}) - SPACE to save", crop_frame(frame_bgr))
            key = cv2.waitKey(1) & 0xFF

            if key == 32:  # SPACE
                save_reference(frame_bgr, ref_type)
                break
            if key == ord('q'):
                print("Quit without saving.")
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Generate/modify QCM occupancy reference images.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_capture = subparsers.add_parser("capture", help="Capture a reference from the camera")
    p_capture.add_argument("type", choices=REF_PATHS.keys(), help="Which reference to save")

    p_crop = subparsers.add_parser("crop", help="Crop an existing image into a reference")
    p_crop.add_argument("type", choices=REF_PATHS.keys(), help="Which reference to save")
    p_crop.add_argument("image", help="Path to the full (uncropped) image")

    args = parser.parse_args()

    if args.command == "capture":
        capture_reference(args.type)
    else:
        crop_existing(args.type, args.image)


if __name__ == "__main__":
    main()
