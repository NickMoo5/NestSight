import time
import os
from enum import Enum
import cv2
from qcm import Qcm
from nestSight import BirdieState
from uart import UARTHandler, TxMsg, RxMsg
import signal

def service_shutdown(signum, frame):
    print(f"Caught signal {signum}, raising KeyboardInterrupt...")
    raise KeyboardInterrupt

# Register the signals
signal.signal(signal.SIGTERM, service_shutdown)
signal.signal(signal.SIGINT, service_shutdown)

POLL_INTERVAL = 1.0  # seconds between READY/occupancy polls

class mainProcess:

    def __init__(self):
        # Qcm init sets everything up, including closing the shutter
        self.qcm = None
        self.uart = None
        try:
            self.qcm = Qcm()
            self.uart = UARTHandler()
            self.uart.start()
        except BaseException:
            # Construction failed partway: release whatever exists so pool
            # workers/GPIO/serial don't get stranded.
            self.cleanup()
            raise

    def cleanup(self):
        if self.qcm is not None:
            self.qcm.cleanup()
        if self.uart is not None:
            try:
                self.uart.stop()
            except Exception as e:
                print(f"[CLEANUP] uart.stop failed: {e}")

    def run(self):
        print("System Ready")

        try:
            while True:
                # Transmit READY and keep checking for a birdie
                self.uart.send(TxMsg.READY)

                state = self.qcm.check_occupancy()
                if state != BirdieState.BIRDIE:
                    time.sleep(POLL_INTERVAL)
                    continue

                # Birdie detected: announce and run the evaluation process
                print("[SYS] Birdie detected! Starting evaluation")
                self.uart.send(TxMsg.EVAL)

                self.qcm.run_evaluation()

                print("[SYS] Evaluation complete, returning to READY")

        except KeyboardInterrupt:
            print("Shutting down...")

        except Exception:
            # Print the real error BEFORE the finally's os._exit silences it
            import traceback
            traceback.print_exc()

        finally:
            self.cleanup()
            os._exit(0)


def main():
    runProcess = None
    try:
        runProcess = mainProcess()
        runProcess.run()
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Only reached if construction failed; run() exits the process itself.
        if runProcess is not None:
            runProcess.cleanup()


# --- Execution ---
if __name__ == "__main__":
    main()


