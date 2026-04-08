import serial
import threading
import queue
import time
from enum import Enum

# =======================
# CONFIG
# =======================
UART_PORT = "/dev/ttyAMA0"   # or "/dev/ttyAMA0" / "/dev/ttyUSB0"
UART_BAUD = 115200

# =======================
# MESSAGE TYPES
# =======================
class RxMsg(Enum):
    EJECT = "EJECT"
    EVAL  = "EVAL"
    N     = "N"
    S     = "S"
    CLEAN = "CLEANUP"
    NONE  = ""

class TxMsg(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    READY = "READY"
    SET = "SET"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"

MSG_MAP = {
    "PASS": TxMsg.PASS,
    "FAIL": TxMsg.FAIL,
    "READY": TxMsg.READY,
    "SET": TxMsg.SET,
    "UNKNOWN": TxMsg.NONE,
    "EJECT" : RxMsg.EJECT,
    "EVAL" : RxMsg.EVAL,
    "N"    : RxMsg.N,
    "S"    : RxMsg.S,
    "NONE" : RxMsg.NONE
}

# =======================
# UART HANDLER
# =======================
class UARTHandler:
    def __init__(self):
        self.ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.01)
        self.tx_queue = queue.Queue(maxsize=10)
        self.rx_queue = queue.Queue(maxsize=20)

        self.running = True

        # RX state
        self.buffer = ""
        self.receiving = False

        # Threads
        self.tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
        self.rx_thread = threading.Thread(target=self._rx_worker, daemon=True)

    # =======================
    # START
    # =======================
    def start(self):
        self.tx_thread.start()
        self.rx_thread.start()

    # =======================
    # FORMAT
    # =======================
    def _format_message(self, msg_type):
        return f"<{msg_type}>"

    # =======================
    # SEND (PUBLIC)
    # =======================
    def send(self, msg_type: TxMsg):
        try:
            self.tx_queue.put_nowait(msg_type.value)
        except queue.Full:
            print("[UART] TX queue full")

    # =======================
    # TX THREAD
    # =======================
    def _tx_worker(self):
        while self.running:
            try:
                msg_type = self.tx_queue.get(timeout=0.1)
                msg = self._format_message(msg_type)

                self.ser.write((msg + "\n").encode())

                print(f"[UART TX] {msg}")

            except queue.Empty:
                continue

    # =======================
    # RX THREAD
    # =======================
    def _rx_worker(self):
        while self.running:
            while self.ser.in_waiting:
                c = self.ser.read().decode(errors="ignore")

                if c == '<':
                    self.buffer = ""
                    self.receiving = True

                elif c == '>' and self.receiving:
                    self.receiving = False

                    msg_type = MSG_MAP.get(self.buffer, RxMsg.NONE) 
                    print(f"[UART RX] {msg_type.value}")
                    try:
                        self.rx_queue.put_nowait(msg_type)
                    except queue.Full:
                        print("[UART] RX queue full")

                elif self.receiving:
                    self.buffer += c

                    # overflow protection
                    if len(self.buffer) > 32:
                        self.buffer = ""
                        self.receiving = False

            time.sleep(0.01)

    def get_message(self) -> RxMsg:
        try:
            return self.rx_queue.get_nowait()
        except queue.Empty:
            return None

    # =======================
    # STOP
    # =======================
    def stop(self):
        self.running = False
        self.ser.close()
        

def main():
    uart = UARTHandler()
    uart.start()

    print("UART started. Type messages or press Ctrl+C to exit.")

    last_send = time.time()

    try:
        while True:
            # Periodic send (every 3 sec)
            if time.time() - last_send > 3:
                uart.send(TxMsg.FAIL)
                last_send = time.time()

            # Manual send from keyboard
            if input_available():
                user_input = input().strip().upper()
                if user_input:
                    uart.send(user_input)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Stopping...")
        uart.stop()


# Non-blocking input check
import sys
import select
def input_available():
    return select.select([sys.stdin], [], [], 0)[0]


if __name__ == "__main__":
    main()