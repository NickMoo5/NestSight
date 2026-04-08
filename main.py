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

class mainProcess:

    def __init__(self):
        self.qcm = Qcm()
        self.uart = UARTHandler()
        self.uart.start()
        self.operation_mode = None
        self.running = False

    def cleanup(self):
        self.qcm.cleanup()
        self.uart.stop()

    def run(self):
        print("System Ready")
        self.uart.send(TxMsg.READY)

        try:
            while True:
                msg = self.uart.get_message()

                if msg is None:
                    time.sleep(0.05)
                    continue

                if not self.operation_mode:
                    if msg == RxMsg.N:
                        print("[SYS] Setting Normal Operation Mode")
                        self.operation_mode = opMode.NORMAL
                        self.qcm.close_shutter()
                        uart.send(TxMsg.SET)

                    elif msg == RxMsg.S:
                        print("[SYS] Setting Skip Operation Mode")
                        self.operation_mode = opMode.SKIP
                        self.qcm.open_shutter()
                        uart.send(TxMsg.SET)
                    else:
                        print(f"ERROR: received unintended msg: {msg.value}")
                # =======================
                # HANDLE COMMANDS
                # =======================
                elif self.operation_mode == opMode.NORMAL or self.running:
                    if msg == RxMsg.EVAL:
                        print("[SYS] Starting evaluation")
                        self.running = True
                        result = self.qcm.evaluate_birdie()

                        print(f"[SYS] Result: {result}")

                        if result == "PASS":
                            self.uart.send(TxMsg.PASS)
                        else:
                            self.uart.send(TxMsg.FAIL)

                    elif msg == RxMsg.EJECT:
                        print("[SYS] Ejecting birdie")
                        self.qcm.drop()
                        self.running = False
                        self.uart.send(TxMsg.READY)

                    else:
                        print(f"ERROR: received unintended msg: {msg.value}")
                elif not self.running:
                    if msg == RxMsg.N:
                        print("[SYS] Setting Normal Operation Mode")
                        self.operation_mode = opMode.NORMAL
                        self.qcm.close_shutter()
                        uart.send(TxMsg.SET)

                    elif msg == RxMsg.S:
                        print("[SYS] Setting Skip Operation Mode")
                        self.operation_mode = opMode.SKIP
                        self.qcm.open_shutter()
                        uart.send(TxMsg.SET)
                    elif msg == RxMsg.CLEANUP:
                        print("[SYS] Cleaning system up")
                        self.operation_mode = None
                        self.qcm.cleanup()
                        
                    else:
                        print(f"ERROR: received unintended msg: {msg.value}")


        except KeyboardInterrupt:
            print("Shutting down...")

        finally:
            self.uart.stop()
            self.qcm.cleanup()


def main():
    runProcess = mainProcess()
    runProcess.run()


# --- Execution ---
if __name__ == "__main__":
    main()


