from array import array
from contextlib import nullcontext
from dataclasses import replace
import sys
from threading import Event
import unittest
from unittest.mock import Mock, patch

from audio_input import (
    BACKENDS, AudioFormat, CaptureError, DefaultInputChanged, Microphone,
    PcmConverter, Route, capture_input, group_routes,
)


class FakeSoundDevice:
    class PortAudioError(Exception):
        pass

    def __init__(self, formats, signals):
        self.formats = formats
        self.signals = signals
        self.tried = []
        self.opened = []

    def check_input_settings(self, device, samplerate, channels, **_):
        request = (device, samplerate, channels)
        self.tried.append(request)
        if request not in self.formats:
            raise self.PortAudioError("Invalid sample rate or channel count", -9997)

    def RawInputStream(self, device, samplerate, channels, callback, **_):
        stream = Mock(active=True)
        self.opened.append((device, samplerate, channels, stream))

        def start():
            amplitude = self.signals[device]
            if isinstance(amplitude, Exception):
                raise amplitude
            if amplitude is not None:
                frames = samplerate // 20
                callback(array("h", [amplitude] * frames * channels).tobytes(), frames, None, None)

        stream.start.side_effect = start
        return stream

    @staticmethod
    def WasapiSettings(**options):
        return options


WASAPI = Route(4, "Micrófono de matriz larga (Realtek(R) Audio)", BACKENDS[0], 48000, 2, "wasapi",
               default=True, endpoint="endpoint-realtek")
MME = Route(7, WASAPI.name[:31], BACKENDS[1], 44100, 1, "mme", default=True)
MAPPER = Route(8, "Asignador de sonido Microsoft - Input", BACKENDS[1], 44100, 1, "mapper",
               mapper=True)
DIRECT = Route(12, WASAPI.name, BACKENDS[2], 44100, 2, "ds")


class RouteTests(unittest.TestCase):
    def test_names_are_grouped_and_legacy_selection_resolves(self):
        inputs = group_routes([WASAPI, MME, DIRECT, MAPPER])
        self.assertEqual(len(inputs.devices), 1)
        self.assertEqual(inputs.key_for("mme"), "endpoint-realtek")
        self.assertEqual(inputs.key_for("mapper"), "")
        self.assertEqual([r.index for r in inputs.routes_for("")], [4, 8, 7, 12])
        self.assertEqual([r.index for r in inputs.routes_for("mapper")], [8, 4, 7, 12])

    def test_ambiguous_names_are_retained_as_separate_devices(self):
        second = replace(WASAPI, index=6, endpoint="other", legacy_key="other")
        inputs = group_routes([WASAPI, second, MME])
        self.assertEqual(len(inputs.devices), 3)
        self.assertEqual(len({item.label for item in inputs.devices}), 3)
        self.assertEqual([r.index for r in inputs.routes_for("other")], [6])

    def test_default_endpoint_override_and_explicit_device_are_distinct(self):
        usb = replace(WASAPI, index=5, name="USB", endpoint="usb", default=False)
        inputs = group_routes([WASAPI, usb, MAPPER])
        self.assertEqual([r.index for r in inputs.routes_for("", "usb")], [5, 8])
        self.assertEqual([r.index for r in inputs.routes_for("endpoint-realtek", "usb")], [4])
        with self.assertRaisesRegex(CaptureError, "desconectado"):
            inputs.routes_for("missing")


class CaptureTests(unittest.TestCase):
    def input(self, driver, selection="", rejected=()):
        self.enterContext(patch("audio_input.portaudio", return_value=nullcontext(driver)))
        self.enterContext(patch("audio_input.sys", Mock(platform="fixture")))
        return self.enterContext(capture_input(
            group_routes([WASAPI, MME, DIRECT, MAPPER]), selection, Event(), rejected,
        ))

    def test_native_stereo_48khz_resamples_to_mono_16khz(self):
        driver = FakeSoundDevice([(4, 48000, 2)], {4: 500})
        capture = self.input(driver, "wasapi")
        pcm = capture.read()
        self.assertEqual(driver.tried, [(4, 48000, 1), (4, 48000, 2)])
        self.assertEqual(len(pcm), 1600)
        self.assertGreater(capture.level, 0)

    def test_silent_wasapi_switches_to_mme_mapper(self):
        self.enterContext(patch("audio_input.DIGITAL_SILENCE", 0.05))
        driver = FakeSoundDevice([(4, 48000, 1), (8, 44100, 1)], {4: 0, 8: 500})
        capture = self.input(driver, "wasapi")
        self.assertEqual(capture.route.index, 8)
        driver.opened[0][3].close.assert_called_once()

    def test_failed_start_and_rejected_backend_leave_directsound(self):
        driver = FakeSoundDevice([(8, 44100, 1), (12, 44100, 1)],
                                 {8: FakeSoundDevice.PortAudioError("start rejected"), 12: 500})
        capture = self.input(driver, rejected={4})
        self.assertEqual(capture.route.index, 12)
        self.assertTrue(all(attempt[0] != 4 for attempt in driver.tried))
        driver.opened[0][3].close.assert_called_once()

    def test_live_default_change_stops_the_current_capture(self):
        driver = FakeSoundDevice([(4, 48000, 1)], {4: 500})
        audio = AudioFormat(48000, 1)
        options = dict(device=4, samplerate=48000, channels=1)
        current = Mock(side_effect=["endpoint-realtek", "new-default"])
        with Microphone(driver, WASAPI, audio, options, current, "endpoint-realtek") as capture:
            self.assertIsNotNone(capture.read())
            capture.default_check_at = 0
            with self.assertRaises(DefaultInputChanged):
                capture.read()

    def test_float_capture_converts_to_signed_pcm(self):
        converter = PcmConverter(AudioFormat(16000, 1, dtype="float32"))
        self.assertEqual(converter.convert(array("f", [-1.5, 0, 1.5]).tobytes()),
                         array("h", [-32767, 0, 32767]).tobytes())

    def test_opposite_stereo_polarity_does_not_cancel(self):
        converter = PcmConverter(AudioFormat(16000, 2))
        raw = array("h", [900, -900, 900, -900]).tobytes()
        self.assertEqual(converter.convert(raw), array("h", [900, 900]).tobytes())


@unittest.skipUnless(sys.platform == "win32", "Necesita Windows")
class NativeAudioTests(unittest.TestCase):
    def test_queries_live_default_and_mappers_even_without_hardware(self):
        from windows_audio import default_input, mapper_names

        with default_input() as current:
            identifier = current()
            self.assertTrue(identifier is None or isinstance(identifier, str))
        self.assertEqual(set(mapper_names()), {BACKENDS[1], BACKENDS[2]})

    def test_dialog_meter_and_explicit_test_use_the_selected_input(self):
        import tkinter as tk

        from jarvis_gui import VoiceDialog
        from preferences import VoiceSettings

        root = tk.Tk()
        test, cancel = Mock(), Mock()
        dialog = VoiceDialog(root, VoiceSettings(), Mock(), Mock(), test, cancel,
                             lambda: (65, "Realtek · WASAPI · 48000 Hz"))
        try:
            root.update()
            self.assertEqual(float(dialog.level["value"]), 65)
            self.assertIn("48000 Hz", dialog.input_route["text"])
            inputs = group_routes([WASAPI, MME])
            dialog.show_catalog(inputs, [], "")
            dialog.microphone.set(inputs.devices[0].label)
            dialog.test_button.invoke()
            test.assert_called_once_with(WASAPI.endpoint)
            self.assertIn("disabled", str(dialog.test_button["state"]))
            dialog.test_result("Señal recibida")
            self.assertEqual(str(dialog.test_button["state"]), "normal")
        finally:
            root.destroy()
        cancel.assert_called_once()
