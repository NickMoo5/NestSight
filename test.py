from turntable import Turntable
from shutter import Shutter
import time

def main():
    shutter = Shutter()
    turntable = Turntable()

    try:
        shutter.open()
        time.sleep(1)
        shutter.close()
        time.sleep(1)
        for i in range(10): 
            turntable.step(speed=0.003)
            time.sleep(0.2)

        shutter.open()
        time.sleep(1)
        shutter.close()
    finally:
        turntable.cleanup()
        shutter.cleanup()

if __name__ == "__main__":
    main()