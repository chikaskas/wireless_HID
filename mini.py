# ==============================================================================
# ESP32-C3 Super Mini - MicroPython BLE to UART Bridge (Robust & Verified)
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

def build_adv_payload(short_name="Pi5"):
    """
    Primary advertisement payload:
      - Flags (3 bytes)
      - Short Name 'Pi5' (5 bytes)
      - 128-bit NUS UUID (18 bytes)
      Total = 26 bytes (strictly within the 31-byte limit!)
    """
    payload = bytearray()
    # Flags: 0x06 (General Discoverable + BR/EDR not supported)
    payload += bytes([2, 0x01, 0x06])
    # Shortened Local Name (0x08)
    sname_b = short_name.encode()
    payload += bytes([len(sname_b) + 1, 0x08]) + sname_b
    # Complete 128-bit Service UUID (0x07)
    uuid_b = bytes(_NUS_UUID)
    payload += bytes([len(uuid_b) + 1, 0x07]) + uuid_b
    return payload

def build_resp_payload(full_name="Pi5-Remote"):
    """
    Scan response payload:
      - Complete Local Name 'Pi5-Remote' (12 bytes <= 31)
    """
    payload = bytearray()
    name_b = full_name.encode()
    payload += bytes([len(name_b) + 1, 0x09]) + name_b
    return payload

class BLEUARTBridge:
    def __init__(self, name="Pi5-Remote"):
        # Hardware UART configuration for ESP32-C3 Super Mini
        # TX=GPIO4, RX=GPIO5 at 115200 baud
        self.uart = UART(1, baudrate=115200, tx=4, rx=5, txbuf=256, rxbuf=256)

        # Onboard Blue LED on ESP32-C3 Super Mini (GPIO8, active LOW: 0=ON, 1=OFF)
        try:
            self.led = Pin(8, Pin.OUT)
            self.led.value(1) # Off initially
        except:
            self.led = None

        self.ble = bluetooth.BLE()
        self.ble.active(False)
        time.sleep_ms(150)
        self.ble.active(True)
        self.ble.irq(self._irq)

        # Register Nordic UART Service
        ((self.handle_tx, self.handle_rx),) = self.ble.gatts_register_services((_UART_SERVICE,))
        
        self.connections = set()
        self.adv_data = build_adv_payload("Pi5")
        self.resp_data = build_resp_payload(name)
        self.advertise()
        print(f"[BLE-UART] Initialized successfully.")
        print(f"[BLE-UART] Broadcasting as: {name} (Short: Pi5)")

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            print(f"[BLE] Connected! (Connection ID: {conn_handle})")
            if self.led:
                self.led.value(0) # Solid ON when connected

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle in self.connections:
                self.connections.remove(conn_handle)
            print(f"[BLE] Disconnected. Re-starting advertisement...")
            if self.led:
                self.led.value(1) # Off
            self.advertise()

        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self.handle_rx:
                data_in = self.ble.gatts_read(self.handle_rx)
                if data_in:
                    # Immediately forward bytes to Pico over UART
                    self.uart.write(data_in)

    def advertise(self, interval_us=100000):
        # 100ms interval for fast discovery
        self.ble.gap_advertise(interval_us, adv_data=self.adv_data, resp_data=self.resp_data)

# Main execution loop with visual heartbeat
if __name__ == "__main__":
    bridge = BLEUARTBridge(name="Pi5-Remote")
    led_state = 1
    while True:
        # If not connected, blink LED every 500ms as a visual heartbeat
        if not bridge.connections and bridge.led:
            led_state = 0 if led_state == 1 else 1
            bridge.led.value(led_state)
            time.sleep_ms(500)
        else:
            time.sleep(1)
