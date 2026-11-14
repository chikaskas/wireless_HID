import bluetooth
import machine
import time
from micropython import const

# UART setup (TX = GPIO 4, RX = GPIO 5)
# Cross-wire: ESP32 TX (GPIO 4) -> Pico RX (GP1)
uart = machine.UART(1, baudrate=115200, tx=machine.Pin(4), rx=machine.Pin(5))

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
TX_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
RX_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

class BLEUART:
    def __init__(self, name="Pi_KVM_Bridge"):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        
        # Enable both standard write and write-without-response to satisfy all browsers
        services = (
            (UART_UUID, (
                (RX_UUID, bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE),
                (TX_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
            )),
        )
        ((self._rx_handle, self._tx_handle),) = self._ble.gatts_register_services(services)
        self._connections = set()
        self._advertise(name)

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print("BLE Connected.")
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.remove(conn_handle)
            print("BLE Disconnected. Re-advertising...")
            self._advertise("Pi_KVM_Bridge")
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self._rx_handle:
                packet = self._ble.gatts_read(self._rx_handle)
                try:
                    # Direct push to hardware UART stream
                    uart.write(packet)
                except Exception as e:
                    print("UART Write Error:", e)

    def _advertise(self, name):
        adv_data = bytearray(b'\x02\x01\x06') + bytearray((len(name) + 1, 0x09)) + name.encode()
        self._ble.gap_advertise(100, adv_data)

print("Starting ESP32-C3 BLE-UART Bridge...")
ble_uart = BLEUART()

while True:
    time.sleep_ms(100)