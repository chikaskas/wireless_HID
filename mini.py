# ==============================================================================
# ESP32-C3 Super Mini - MicroPython BLE to UART Bridge
# ==============================================================================
# Description:
#   Acts as a BLE Peripheral providing the standard Nordic UART Service (NUS).
#   Receives HID command packets from the Web BLE client and forwards them
#   via hardware UART to the RP2040 (Orpheus Pico).
#
# Hardware Connections:
#   ESP32-C3 GPIO4 (TX) -> RP2040 GP1 (RX)
#   ESP32-C3 GPIO5 (RX) -> RP2040 GP0 (TX) [Optional]
#   ESP32-C3 GND        -> RP2040 GND
#   ESP32-C3 5V/VCC     -> RP2040 VBUS (5V from Pi USB)
# ==============================================================================

import bluetooth
import time
from machine import Pin, UART
from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

# Nordic UART Service (NUS) UUIDs
_NUS_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_RX_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
_TX_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

_FLAG_WRITE = const(0x0008)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_NOTIFY = const(0x0010)

_UART_SERVICE = (
    _NUS_UUID,
    (
        (_TX_UUID, _FLAG_NOTIFY),
        (_RX_UUID, _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
    ),
)

def advertising_payload(name=None, services=None):
    """Builds standard BLE advertisement payload."""
    payload = bytearray()

    def _append(adv_type, value):
        nonlocal payload
        payload += bytes([len(value) + 1, adv_type]) + value

    # General Discoverable Mode & BR/EDR not supported
    _append(0x01, bytes([0x06]))

    if name:
        _append(0x09, name.encode())

    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 2:
                _append(0x03, b)
            elif len(b) == 16:
                _append(0x07, b)

    return payload

class BLEUARTBridge:
    def __init__(self, name="Pi5-Remote"):
        # Hardware UART configuration for ESP32-C3
        # TX=GPIO4, RX=GPIO5 at 115200 baud
        self.uart = UART(1, baudrate=115200, tx=Pin(4), rx=Pin(5))

        # Onboard LED on ESP32-C3 Super Mini (GPIO8, active low)
        try:
            self.led = Pin(8, Pin.OUT)
            self.led.value(1) # Off initially
        except:
            self.led = None

        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        # Register Nordic UART Service
        ((self.handle_tx, self.handle_rx),) = self.ble.gatts_register_services((_UART_SERVICE,))
        
        self.connections = set()
        self.payload = advertising_payload(name=name, services=[_NUS_UUID])
        self.advertise()
        print(f"[BLE-UART] Ready. Device name: {name}")

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            print(f"[BLE] Central connected (Handle: {conn_handle})")
            if self.led:
                self.led.value(0) # Turn LED ON when connected

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle in self.connections:
                self.connections.remove(conn_handle)
            print(f"[BLE] Central disconnected (Handle: {conn_handle})")
            if self.led:
                self.led.value(1) # Turn LED OFF when disconnected
            self.advertise()

        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self.handle_rx:
                # Read incoming data from Web BLE
                data_in = self.ble.gatts_read(self.handle_rx)
                if data_in:
                    # Instantly forward bytes directly over hardware UART to the Pico
                    self.uart.write(data_in)

    def advertise(self, interval_us=50000):
        print("[BLE] Advertising started...")
        self.ble.gap_advertise(interval_us, adv_data=self.payload)

# Entry point
if __name__ == "__main__":
    bridge = BLEUARTBridge(name="Pi5-Remote")
    while True:
        time.sleep(1)
