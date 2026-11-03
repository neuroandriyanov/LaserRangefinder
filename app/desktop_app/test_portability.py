"""First-launch configuration must not contact an author's instrument."""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .model import DEFAULTS, SettingsStore, validate_settings
from .workers import DeviceWorker


class PortabilityTests(unittest.TestCase):
    def test_blank_port_does_not_open_serial(self):
        worker = DeviceWorker('fpga', DEFAULTS, lambda event: None)
        with patch('serial.Serial', side_effect=AssertionError('Unexpected serial access')):
            with self.assertRaises(ValueError):
                worker.run_fpga()

    def test_blank_bluetooth_address_does_not_open_transport(self):
        worker = DeviceWorker('vector', DEFAULTS, lambda event: None)
        with patch('vector60_winusb.WinUsbVector.open', side_effect=AssertionError('Unexpected USB access')):
            with self.assertRaises(ValueError):
                asyncio.run(worker.run_vector())

    def test_device_choices_survive_restart(self):
        settings = deepcopy(DEFAULTS)
        settings.update(port='COM18', vector_address='AA:BB:CC:DD:EE:FF',
                        vector_usb_transport='usb:1234:5678')
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory)/'settings.json')
            store.save(settings)
            self.assertEqual(SettingsStore(store.path).load()[0], settings)

    def test_invalid_transport_rejected(self):
        for transport in ('usb:', 'usb:12:abcd', 'tcp:host:80', None):
            with self.assertRaises(ValueError):
                validate_settings(dict(DEFAULTS, vector_usb_transport=transport))
