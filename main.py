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
        self.operation_mode = None
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

                time.sleep(0.05)

                if msg == RxMsg.CLEANUP and not self.running:
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
                        print(f"ERROR: received unintended msg: {msg.value}")
                # =======================
                # HANDLE COMMANDS
                # =======================
                elif self.operation_mode == opMode.NORMAL:
                    if not self.running:
                        if msg == RxMsg.EVAL:
                            print("[SYS] Starting evaluation")
                            self.running = True
                            result = self.qcm.evaluate_birdie()

                            print(f"[SYS] Result: {result}")

                            if result == "PASS":
                                self.uart.send(TxMsg.PASS)
                            else:
                                self.uart.send(TxMsg.FAIL)
                        else:
                            print(f"ERROR running: received unintended msg: {msg.value}")
                    elif self.running:
                        if msg == RxMsg.EJECT:
                            print("[SYS] Ejecting birdie")
                            self.qcm.drop()
                            self.running = False
                            self.uart.send(TxMsg.READY)

                        else:
                            print(f"ERROR running: received unintended msg: {msg.value}")
                elif self.operation_mode == opMode.SKIP:
                    if not self.skip_mode_on:
                        self.qcm.open_shutter()
                        self.skip_mode_on = True
                        print("[SYS] SKIP mode activated. Opening Shutter")
                    else:
                        print(f"ERROR not running: received unintended msg: {msg.value}")


        except KeyboardInterrupt:
            print("Shutting down...")

        finally:
            self.cleanup()
            os._exit(0)


def main():
    try:
        runProcess = mainProcess()
        runProcess.run()
    except KeyboardInterrupt:
        runProcess.clean()
    finally:
        runProcess.clean()


# --- Execution ---
if __name__ == "__main__":
    main()


