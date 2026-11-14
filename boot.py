import storage
import board
import digitalio

button = digitalio.DigitalInOut(board.GP25)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

if button.value:
    storage.disable_usb_drive()   