import time
import os
from enum import Enum
import cv2
from qcm import Qcm
from uart import UARTHandler, TxMsg, RxMsg
from enum import Enum

class opMode(Enum):
    NORMAL = "NORMAL"
    SKIP = "SKIP"
    IDLE = "IDLE"

class mainProcess:

    def __init__(self):
        self.qcm = Qcm()
        self.uart = UARTHandler()
        self.uart.start()
        self.operation_mode = opMode.IDLE
        self.running = False
        self.skip_mode_on = False

    def cleanup(self):
        self.qcm.cleanup()
        self.uart.stop()

    def run(self):
        print("System Ready")
        self.uart.send(TxMsg.READY)

        try:
            while True:
                msg = self.uart.get_message()

                # Safe display value for logging (handles None)
                msg_val = msg.value if msg is not None else None

                if msg == RxMsg.CLEANUP:
                    print("[SYS] Cleaning system up")
                    self.operation_mode = opMode.IDLE
                    self.qcm.turntableHome()
                    self.qcm.turntableOff()

                if self.operation_mode == opMode.IDLE:
                    if msg is None:
                        self.uart.send(TxMsg.READY)
                    elif msg == RxMsg.N:
                        print("[SYS] Setting Normal Operation Mode")
                        self.operation_mode = opMode.NORMAL
                        self.qcm.close_shutter()
                        self.qcm.turntableOn()
                        self.uart.send(TxMsg.SET)

                    elif msg == RxMsg.S:
                        print("[SYS] Setting Skip Operation Mode")
                        self.operation_mode = opMode.SKIP
                        self.qcm.open_shutter()
                        self.uart.send(TxMsg.SET)
                    else:
                        print(f"ERROR: received unintended msg: {msg_val}")
                # =======================
                # HANDLE COMMANDS
                # =======================
                elif self.operation_mode == opMode.NORMAL:
                    if not self.running:
                        # If there's no message, just wait for commands instead of treating as an error
                        if msg is None:
                            pass
                        elif msg == RxMsg.EVAL:
                            print("[SYS] Starting evaluation")
                            self.running = True
                            result = self.qcm.evaluate_birdie()

                            print(f"[SYS] Result: {result}")

                            if result == "PASS":
                                self.uart.send(TxMsg.PASS)
                            else:
                                self.uart.send(TxMsg.FAIL)
                        else:
                            print(f"ERROR running: received unintended msg: {msg_val}")
                            continue
                    elif self.running:
                        if msg == RxMsg.EJECT:
                            print("[SYS] Ejecting birdie")
                            self.qcm.drop()
                            self.running = False
                            self.uart.send(TxMsg.READY)

                        elif msg is None:
                            pass
                        else:
                            print(f"ERROR running: received unintended msg: {msg_val}")
                            continue
                elif self.operation_mode == opMode.SKIP:
                    if not self.skip_mode_on:
                        self.qcm.open_shutter()
                        self.skip_mode_on = True
                        print("[SYS] SKIP mode activated. Opening Shutter")
                    elif msg is None:
                        pass
                    else:
                        print(f"ERROR not running: received unintended msg: {msg_val}")
                        continue

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("Shutting down...")

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
        if runProcess is not None:
            runProcess.cleanup()
        os.system("sudo pkill -9 python")


# --- Execution ---
if __name__ == "__main__":
    main()


