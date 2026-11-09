"""Device selection tests use fake hardware and temporary preferences only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import devices, interface

MICS = [{"id": "usb-mic", "name": "USB microphone", "index": 7, "host": "WASAPI"}]
CAMERAS = [{"id": "usb-camera", "name": "USB camera", "index": 2, "backend": 700}]
SCAN_MICROPHONES = devices._scan_microphones


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        for patcher in (
            patch.object(devices, "SETTINGS_PATH", Path(self.folder.name) / "devices.json"),
            patch.object(devices, "_preferences", {"microphone": "", "camera": ""}),
            patch.object(devices, "_catalog", None),
            patch.object(devices, "_scan_microphones", return_value=MICS),
            patch.object(devices, "_scan_cameras", return_value=CAMERAS),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        devices._microphone_changed.clear()
        self.addCleanup(devices._microphone_changed.clear)

    def test_choices_persist_and_route_to_real_indices(self):
        result = devices.select_devices("usb-mic", "usb-camera")
        self.assertEqual(devices.camera_settings(), (2, 700))
        sd = Mock()
        sd.query_devices.return_value = {"default_samplerate": 48000}
        with patch.dict(sys.modules, {"sounddevice": sd}):
            self.assertEqual(devices.microphone_settings(), (7, 16000))
        sd.check_input_settings.assert_called_with(device=7, channels=1, dtype="float32", samplerate=16000)
        self.assertEqual(json.loads(devices.SETTINGS_PATH.read_text()), result["selected"])
        self.assertTrue(interface.has_pending_input())
        self.assertTrue(devices.consume_microphone_change())

    def test_native_rate_is_used_when_microphone_rejects_16khz(self):
        devices.select_devices("usb-mic", "")
        sd = Mock()
        sd.query_devices.return_value = {"default_samplerate": 48000}
        sd.check_input_settings.side_effect = [RuntimeError("Unsupported rate"), None]
        with patch.dict(sys.modules, {"sounddevice": sd}):
            self.assertEqual(devices.microphone_settings(), (7, 48000))

    def test_unknown_or_disconnected_choices_do_not_overwrite_preferences(self):
        devices.select_devices("usb-mic", "usb-camera")
        with self.assertRaises(ValueError):
            devices.select_devices("unknown", "usb-camera")
        self.assertEqual(devices._preferences["microphone"], "usb-mic")
        with patch.object(devices, "_scan_cameras", return_value=[]):
            devices.list_devices(refresh=True)
            with self.assertRaisesRegex(RuntimeError, "disconnected"):
                devices.camera_settings()

    def test_default_selection_uses_system_input_and_default_camera(self):
        devices.select_devices("", "")
        sd = Mock()
        with patch.dict(sys.modules, {"sounddevice": sd}):
            self.assertEqual(devices.microphone_settings(), (None, 16000))
        self.assertEqual(devices.camera_settings(), (0, 0))

    def test_refresh_reports_new_devices_and_partial_failures(self):
        with patch.object(devices, "_scan_microphones", side_effect=ImportError("audio missing")):
            result = devices.list_devices(refresh=True)
        self.assertEqual(result["microphones"], [])
        self.assertEqual(result["cameras"], CAMERAS)
        self.assertIn("microphone", result["errors"])

    def test_camera_only_change_does_not_interrupt_microphone(self):
        devices.select_devices("", "usb-camera")
        self.assertFalse(devices.microphone_changed())

    def test_reapplying_current_choices_retries_microphone(self):
        devices.select_devices("usb-mic", "usb-camera")
        devices.consume_microphone_change()
        devices.select_devices("usb-mic", "usb-camera")
        self.assertTrue(devices.microphone_changed())

    def test_duplicate_audio_apis_do_not_hide_identical_physical_microphones(self):
        sd = Mock()
        sd.query_hostapis.return_value = [{"name": "MME"}, {"name": "Windows WASAPI"}]
        sd.query_devices.return_value = [
            {"name": "USB microphone", "hostapi": host, "max_input_channels": 1}
            for host in (0, 0, 1, 1)
        ]
        with patch.dict(sys.modules, {"sounddevice": sd}):
            items = SCAN_MICROPHONES()
        self.assertEqual(len(items), 2)
        self.assertEqual([item["index"] for item in items], [2, 3])
        self.assertEqual([item["name"] for item in items], ["USB microphone", "USB microphone (2)"])


if __name__ == "__main__":
    unittest.main()
