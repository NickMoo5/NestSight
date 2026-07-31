import time
import os
import socket
from enum import Enum
import cv2
from qcm import Qcm
from nestSight import BirdieState
from uart import UARTHandler, TxMsg, RxMsg
import signal

READY_LOG_INTERVAL = 5  # only log every Nth READY message to keep logs readable
POLL_INTERVAL = 0.2  # seconds between READY/occupancy polls

def sd_notify(msg):
    """Send a notification to systemd (no-op when not run under systemd)."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(addr)
            s.sendall(msg.encode())
    except OSError:
        pass

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
        sd_notify("READY=1")  # init done, systemd can consider us started
        ready_count = 0
        qcm_enabled = True  # Qcm starts enabled with the shutter closed
        fault_flag = False  # set locally (e.g. occupancy ERROR) to trigger the halt block

        try:
            while True:
                # Pet the systemd watchdog: proves the main loop is alive
                sd_notify("WATCHDOG=1")

                # Halt if a FAULT came in (including during a just-finished eval)
                # or was raised locally via fault_flag
                if fault_flag or self._fault_received():
                    print("[SYS] FAULT received! System halted, Ctrl+C to shut down")
                    self.qcm.open_shutter()
                    while True:
                        time.sleep(1)
                        sd_notify("WATCHDOG=1")  # intentionally halted, not hung

                # QCM enable switch: when disabled, keep sending READY but
                # skip evaluation and leave the shutter open
                enabled = self.qcm.is_enabled()
                if enabled != qcm_enabled:
                    qcm_enabled = enabled
                    if enabled:
                        print("[SYS] QCM enabled, closing shutter and resuming evaluation")
                        self.qcm.close_shutter()
                        time.sleep(0.8)
                    else:
                        print("[SYS] QCM disabled, opening shutter and pausing evaluation")
                        self.qcm.open_shutter()
                        self.qcm.close_slide()
                        time.sleep(0.8)

                # Check for a birdie BEFORE signalling READY, so one already
                # in the QCM at startup gets evaluated before the first READY
                if qcm_enabled:
                    state = self.qcm.check_occupancy()
                    if state == BirdieState.BIRDIE:
                        # Birdie detected: announce and run the evaluation process
                        print("[SYS] Birdie detected! Starting evaluation")
                        self.uart.send(TxMsg.EVAL)
                        time.sleep(0.3)  # give the birdie a moment to settle before evaluation
                        self.qcm.run_evaluation()
                        time.sleep(0.7)  # give the birdie a moment to leave before resuming READY

                        print("[SYS] Evaluation complete, returning to READY")
                        # Re-check faults/occupancy before sending READY
                        continue
                    if state == BirdieState.ERROR:
                        # Module contents match neither reference: re-check
                        # after a short settle, and if still in ERROR report
                        # a FAULT over UART and halt via the fault block at
                        # the top of the loop.
                        time.sleep(0.8)
                        if self.qcm.check_occupancy() == BirdieState.ERROR:
                            print("[SYS] Occupancy ERROR: module doesn't match empty or birdie reference")
                            self.uart.send(TxMsg.FAULT)
                            fault_flag = True
                        time.sleep(POLL_INTERVAL)
                        continue

                # QCM is empty (or disabled): safe to transmit READY
                ready_count += 1
                self.uart.send(TxMsg.READY, log=(ready_count % READY_LOG_INTERVAL == 0))
                time.sleep(POLL_INTERVAL)

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


