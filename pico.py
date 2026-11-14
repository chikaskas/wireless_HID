# ==============================================================================
# Hack Club Orpheus Pico (RP2040) - CircuitPython UART to USB HID
# ==============================================================================
# Description:
#   Listens on UART (GP1 RX) for commands forwarded by the ESP32-C3 Super Mini.
#   Translates packets into native USB Keyboard & Mouse HID events sent to Pi 5.
#
# Hardware Connections:
#   RP2040 GP1 (RX)    <- ESP32-C3 GPIO4 (TX)
#   RP2040 GP0 (TX)    -> ESP32-C3 GPIO5 (RX) [Optional]
#   RP2040 GND         -- ESP32-C3 GND
#   RP2040 VBUS (5V)   -- ESP32-C3 5V/VCC
#   RP2040 USB Type-C  -> Raspberry Pi 5 USB Port
# ==============================================================================

import time
import board
import busio
import usb_hid

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse

# Initialize USB HID devices
time.sleep(1) # Allow USB enumeration
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
mouse = Mouse(usb_hid.devices)

# Initialize UART
# GP0 = TX, GP1 = RX
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0.01)

# Keycode lookup dictionary
KEY_MAP = {
    "CTRL": Keycode.CONTROL,
    "ALT": Keycode.ALT,
    "SHIFT": Keycode.SHIFT,
    "GUI": Keycode.GUI,
    "SUPER": Keycode.GUI,
    "ENTER": Keycode.ENTER,
    "RETURN": Keycode.RETURN,
    "TAB": Keycode.TAB,
    "ESC": Keycode.ESCAPE,
    "ESCAPE": Keycode.ESCAPE,
    "BACKSPACE": Keycode.BACKSPACE,
    "SPACE": Keycode.SPACEBAR,
    "UP": Keycode.UP_ARROW,
    "DOWN": Keycode.DOWN_ARROW,
    "LEFT": Keycode.LEFT_ARROW,
    "RIGHT": Keycode.RIGHT_ARROW,
}

# Add A-Z and 0-9 to Keycode lookup
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if hasattr(Keycode, char):
        KEY_MAP[char] = getattr(Keycode, char)
for digit in "0123456789":
    name = ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"][int(digit)]
    if hasattr(Keycode, name):
        KEY_MAP[digit] = getattr(Keycode, name)

# Track active mouse button state
current_mouse_buttons = 0

def handle_mouse_packet(packet):
    """Parses M:<buttons>:<dx>:<dy>:<wheel>"""
    global current_mouse_buttons
    try:
        parts = packet.split(":")
        if len(parts) < 5:
            return
        btn_mask = int(parts[1])
        dx = int(parts[2])
        dy = int(parts[3])
        wheel = int(parts[4])

        # Mouse relative movement & scroll
        if dx != 0 or dy != 0 or wheel != 0:
            mouse.move(x=dx, y=dy, wheel=wheel)

        # Handle button presses/releases
        if btn_mask != current_mouse_buttons:
            # Left button (Bit 0)
            if (btn_mask & 1) and not (current_mouse_buttons & 1):
                mouse.press(Mouse.LEFT_BUTTON)
            elif not (btn_mask & 1) and (current_mouse_buttons & 1):
                mouse.release(Mouse.LEFT_BUTTON)

            # Right button (Bit 1)
            if (btn_mask & 2) and not (current_mouse_buttons & 2):
                mouse.press(Mouse.RIGHT_BUTTON)
            elif not (btn_mask & 2) and (current_mouse_buttons & 2):
                mouse.release(Mouse.RIGHT_BUTTON)

            # Middle button (Bit 2)
            if (btn_mask & 4) and not (current_mouse_buttons & 4):
                mouse.press(Mouse.MIDDLE_BUTTON)
            elif not (btn_mask & 4) and (current_mouse_buttons & 4):
                mouse.release(Mouse.MIDDLE_BUTTON)

            current_mouse_buttons = btn_mask
    except Exception as e:
        print("Mouse parse error:", e)

def handle_key_packet(packet):
    """Parses K:<action>:<key_name> (Action: D=Down, U=Up, P=Press/Tap)"""
    try:
        parts = packet.split(":")
        if len(parts) < 3:
            return
        action = parts[1].upper()
        key_name = parts[2].strip().upper()

        code = KEY_MAP.get(key_name)
        if code is None:
            # Fallback if Keycode has the attribute directly
            if hasattr(Keycode, key_name):
                code = getattr(Keycode, key_name)

        if code is not None:
            if action == "D":
                kbd.press(code)
            elif action == "U":
                kbd.release(code)
            elif action == "P":
                kbd.send(code)
    except Exception as e:
        print("Key parse error:", e)

def handle_text_packet(packet):
    """Parses T:<string> and types it out verbatim"""
    try:
        text = packet[2:] # Strip 'T:'
        layout.write(text)
    except Exception as e:
        print("Text parse error:", e)

print("[Orpheus-HID] Ready. Listening on UART (GP1 RX)...")

# Main loop: process incoming UART stream
rx_buffer = bytearray()

while True:
    data = uart.read(64)
    if data:
        rx_buffer.extend(data)
        while b"\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split(b"\n", 1)
            try:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                if line_str.startswith("M:"):
                    handle_mouse_packet(line_str)
                elif line_str.startswith("K:"):
                    handle_key_packet(line_str)
                elif line_str.startswith("T:"):
                    handle_text_packet(line_str)
            except Exception as e:
                print("Buffer decoding error:", e)
