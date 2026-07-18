import time
import os
from enum import Enum
import cv2
from qcm import Qcm
from nestSight import BirdieState
from uart import UARTHandler, TxMsg, RxMsg
import signal

READY_LOG_INTERVAL = 5  # only log every Nth READY message to keep logs readable

def service_shutdown(signum, frame):
    print(f"Caught signal {signum}, raising KeyboardInterrupt...")
    raise KeyboardInterrupt

# Register the signals
signal.signal(signal.SIGTERM, service_shutdown)
signal.signal(signal.SIGINT, service_shutdown)

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

    def _fault_received(self):
        # Drain any pending RX messages, looking for a FAULT
        msg = self.uart.get_message()
        while msg is not None:
            if msg == RxMsg.FAULT:
                return True
            msg = self.uart.get_message()
        return False

    def run(self):
        print("System Ready")
        ready_count = 0

        try:
            while True:
                # Halt if a FAULT came in (including during a just-finished eval)
                if self._fault_received():
                    print("[SYS] FAULT received! System halted, Ctrl+C to shut down")
                    while True:
                        time.sleep(1)

                # Transmit READY and keep checking for a birdie
                ready_count += 1
                self.uart.send(TxMsg.READY, log=(ready_count % READY_LOG_INTERVAL == 0))

                state = self.qcm.check_occupancy()
                if state != BirdieState.BIRDIE:
                    continue

                # Birdie detected: announce and run the evaluation process
                print("[SYS] Birdie detected! Starting evaluation")

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


