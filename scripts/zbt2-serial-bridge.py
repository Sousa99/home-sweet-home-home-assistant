#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pyserial>=3.5,<4"]
# ///
"""Expose the macOS ZBT-2 serial port to Home Assistant over RFC2217."""

from __future__ import annotations

import argparse
import glob
import logging
import socket
import threading
from typing import Any

import serial
import serial.rfc2217


LOGGER = logging.getLogger("zbt2-serial-bridge")


class SerialRedirector:
    def __init__(self, serial_port: serial.Serial, client: socket.socket) -> None:
        self.serial_port = serial_port
        self.client = client
        self.alive = True
        self.write_lock = threading.Lock()
        self.rfc2217 = serial.rfc2217.PortManager(self.serial_port, self)
        self._patch_rfc2217_mask_ack()

    def _patch_rfc2217_mask_ack(self) -> None:
        # serialx expects acknowledgements for mask commands that pyserial's
        # reference server applies without acknowledging.
        original = self.rfc2217._telnet_process_subnegotiation

        def process(suboption: bytes) -> None:
            original(suboption)
            if suboption[:1] != serial.rfc2217.COM_PORT_OPTION:
                return
            if suboption[1:2] == serial.rfc2217.SET_MODEMSTATE_MASK:
                response = serial.rfc2217.SERVER_SET_MODEMSTATE_MASK
            elif suboption[1:2] == serial.rfc2217.SET_LINESTATE_MASK:
                response = serial.rfc2217.SERVER_SET_LINESTATE_MASK
            else:
                return
            self.rfc2217.rfc2217_send_subnegotiation(response, suboption[2:3])

        self.rfc2217._telnet_process_subnegotiation = process

    def write(self, data: bytes) -> None:
        with self.write_lock:
            self.client.sendall(data)

    def serial_to_client(self) -> None:
        try:
            while self.alive:
                data = self.serial_port.read(self.serial_port.in_waiting or 1)
                if data:
                    self.write(b"".join(self.rfc2217.escape(data)))
        except (OSError, serial.SerialException) as exc:
            LOGGER.debug("Serial reader stopped: %s", exc)
        finally:
            self.alive = False

    def statusline_poller(self) -> None:
        while self.alive:
            try:
                self.rfc2217.check_modem_lines()
            except (OSError, serial.SerialException) as exc:
                LOGGER.debug("Modem line polling stopped: %s", exc)
                self.alive = False
                return
            threading.Event().wait(1)

    def client_to_serial(self) -> None:
        try:
            while self.alive:
                data = self.client.recv(4096)
                if not data:
                    break
                self.serial_port.write(b"".join(self.rfc2217.filter(data)))
        except (OSError, serial.SerialException) as exc:
            LOGGER.debug("Client reader stopped: %s", exc)
        finally:
            self.alive = False

    def run(self) -> None:
        reader = threading.Thread(target=self.serial_to_client, daemon=True)
        status = threading.Thread(target=self.statusline_poller, daemon=True)
        reader.start()
        status.start()
        self.client_to_serial()
        self.alive = False
        reader.join(timeout=2)
        status.join(timeout=2)


def find_serial_port(explicit_port: str | None) -> str:
    if explicit_port:
        return explicit_port

    candidates = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/cu.usbserial*"))
    if len(candidates) != 1:
        raise RuntimeError(
            "Set ZBT2_SERIAL_PORT or --serial-port; expected one USB serial device, "
            f"found {candidates!r}"
        )
    return candidates[0]


def serve(serial_port: str, host: str, port: int) -> None:
    settings: dict[str, Any] = {
        "baudrate": 460800,
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "rtscts": True,
        "xonxoff": False,
        "timeout": 1,
    }

    with serial.serial_for_url(serial_port, do_not_open=True, **settings) as serial_port_handle:
        serial_port_handle.rts = True
        serial_port_handle.dtr = True
        LOGGER.info("Serving %s on %s:%s", serial_port, host, port)

        with socket.create_server((host, port), backlog=1) as server:
            while True:
                client, address = server.accept()
                LOGGER.info("Home Assistant connected from %s", address)
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try:
                    SerialRedirector(serial_port_handle, client).run()
                finally:
                    client.close()
                    LOGGER.info("Home Assistant disconnected")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial-port", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6638)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    serve(find_serial_port(args.serial_port), args.host, args.port)


if __name__ == "__main__":
    main()
