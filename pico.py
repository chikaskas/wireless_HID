import board
import busio
import time
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

# Give the Raspberry Pi 5 USB host controller time to fully enumerate on boot
time.sleep(2.0)

try:
    kbd = Keyboard(usb_hid.devices)
except Exception as e:
    print("HID Device initialization failed. Check boot.py configuration:", e)

# Initialize UART (Pico RX = GP1, TX = GP0)
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0.05)

print("Orpheus Pico USB HID Bridge Online.")

while True:
    data = uart.read(1)
    if data:
        try:
            char = data.decode('utf-8')
            if char == '\n' or char == '\r':
                kbd.send(Keycode.ENTER)
            elif char == '\b' or char == '\x7f':
                kbd.send(Keycode.BACKSPACE)
            else:
                kbd.write(char)
        except UnicodeError:
            pass # Ignore malformed multi-byte packet chunks
        except Exception as e:
            print("HID Typing Error:", e)
            
    time.sleep(0.005)