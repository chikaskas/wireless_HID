# ==============================================================================
# Hack Club Orpheus Pico (RP2040) - CircuitPython UART to USB HID (Hardened)
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
time.sleep(1) # USB enumeration delay
try:
    kbd = Keyboard(usb_hid.devices)
    layout = KeyboardLayoutUS(kbd)
    mouse = Mouse(usb_hid.devices)
except Exception as e:
    print("HID init error:", e)

# Hardware UART on RP2040: GP0 = TX, GP1 = RX
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0.01)

# Keycode lookup dictionary
KEY_MAP = {
    "CTRL": Keycode.CONTROL,
    "CONTROL": Keycode.CONTROL,
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

# Dynamically populate A-Z and 0-9
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if hasattr(Keycode, char):
        KEY_MAP[char] = getattr(Keycode, char)
for digit in "0123456789":
    names = ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]
    name = names[int(digit)]
    if hasattr(Keycode, name):
        KEY_MAP[digit] = getattr(Keycode, name)

current_mouse_buttons = 0

def clamp(val, min_v=-127, max_v=127):
    """Clamps integer to fit inside signed 8-bit HID descriptor limits."""
    return max(min_v, min(max_v, val))

def handle_mouse_packet(packet):
    """Parses M:<buttons>:<dx>:<dy>:<wheel>"""
    global current_mouse_buttons
    try:
        parts = packet.split(":")
        if len(parts) < 5:
            return
        btn_mask = int(parts[1])
        # Crucial: Clamp to -127..127 to prevent struct.pack OverflowError
        dx = clamp(int(parts[2]))
        dy = clamp(int(parts[3]))
        wheel = clamp(int(parts[4]))

        if dx != 0 or dy != 0 or wheel != 0:
            mouse.move(x=dx, y=dy, wheel=wheel)

        if btn_mask != current_mouse_buttons:
            # Left (Bit 0)
            if (btn_mask & 1) and not (current_mouse_buttons & 1):
                mouse.press(Mouse.LEFT_BUTTON)
            elif not (btn_mask & 1) and (current_mouse_buttons & 1):
                mouse.release(Mouse.LEFT_BUTTON)

            # Right (Bit 1)
            if (btn_mask & 2) and not (current_mouse_buttons & 2):
                mouse.press(Mouse.RIGHT_BUTTON)
            elif not (btn_mask & 2) and (current_mouse_buttons & 2):
                mouse.release(Mouse.RIGHT_BUTTON)

            # Middle (Bit 2)
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
        if code is None and hasattr(Keycode, key_name):
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
    """Parses T:<string> and types characters verbatim."""
    try:
        text = packet[2:] # Strip 'T:'
        layout.write(text)
    except Exception as e:
        print("Text parse error:", e)

def reset_all_inputs():
    """Failsafe release of all held keys and mouse buttons."""
    global current_mouse_buttons
    try:
        kbd.release_all()
        mouse.release_all()
        current_mouse_buttons = 0
    except:
        pass

print("[Orpheus-HID] Ready. Listening on UART GP1 (RX)...")

rx_buffer = bytearray()

while True:
    data = uart.read(64)
    if data:
        rx_buffer.extend(data)
        while b"\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split(b"\n", 1)
            try:
                line_str = line.decode("utf-8").strip("\r\n")
                if not line_str:
                    continue

                if line_str.startswith("M:"):
                    handle_mouse_packet(line_str)
                elif line_str.startswith("K:"):
                    handle_key_packet(line_str)
                elif line_str.startswith("T:"):
                    handle_text_packet(line_str)
                elif line_str.startswith("R:ALL"):
                    reset_all_inputs()
            except Exception as e:
                print("Decode error:", e)
