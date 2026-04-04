import serial
import threading
import queue
import time

# =======================
# CONFIG
# =======================
UART_PORT = "/dev/serial0"   # or "/dev/ttyAMA0" / "/dev/ttyUSB0"
UART_BAUD = 115200

# =======================
# MESSAGE TYPES
# =======================
class RxMsg:
    PASS = "PASS"
    FAIL = "FAIL"
    READY = "READY"
    SET = "SET"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"

class TxMsg:
    EJECT = "EJECT"
    EVAL  = "EVAL"
    N     = "N"
    S     = "S"
    NONE  = ""

# =======================
# UART HANDLER
# =======================
class UARTHandler:
    def __init__(self):
        self.ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.01)
        self.tx_queue = queue.Queue(maxsize=10)

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
    # PARSE
    # =======================
    def _parse_message(self, msg):
        if msg == "PASS": return RxMsg.PASS
        if msg == "FAIL": return RxMsg.FAIL
        if msg == "READY": return RxMsg.READY
        if msg == "SET": return RxMsg.SET
        if msg == "": return RxMsg.NONE
        return RxMsg.UNKNOWN

    # =======================
    # SEND (PUBLIC)
    # =======================
    def send(self, msg_type):
        try:
            self.tx_queue.put_nowait(msg_type)
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

                    msg_type = self._parse_message(self.buffer)

                    self._handle_message(msg_type)

                elif self.receiving:
                    self.buffer += c

                    # overflow protection
                    if len(self.buffer) > 32:
                        self.buffer = ""
                        self.receiving = False

            time.sleep(0.01)

    # =======================
    # USER HANDLER
    # =======================
    def _handle_message(self, msg_type):
        if msg_type == RxMsg.PASS:
            print("YES")

        elif msg_type == RxMsg.FAIL:
            print("YES2")

        elif msg_type == RxMsg.READY:
            print("ESP READY")

        elif msg_type == RxMsg.SET:
            print("SET RECEIVED")

        elif msg_type == RxMsg.UNKNOWN:
            print("UNKNOWN MSG")

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
                uart.send(TxMsg.EVAL)
                print("Sent: <EVAL>")
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