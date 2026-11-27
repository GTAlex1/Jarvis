from array import array
from contextlib import nullcontext
from dataclasses import replace
import sys
from threading import Event
import unittest
from unittest.mock import Mock, patch

from audio_input import (
    BACKENDS, AudioFormat, CaptureError, DefaultInputChanged, Microphone,
    PcmConverter, Route, capture_input, group_routes, input_formats, reject_recognition,
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

    def RawInputStream(self, device, samplerate, channels, callback, dtype="int16", **_):
        stream = Mock(active=True)
        self.opened.append((device, samplerate, channels, stream))

        def start():
            amplitude = self.signals[device]
            if isinstance(amplitude, Exception):
                raise amplitude
            if amplitude is not None:
                frames = samplerate // 20
                sample = array("f", [amplitude / 32768]) if dtype == "float32" else array("h", [amplitude])
                callback((sample * frames * channels).tobytes(), frames, None, None)

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
        self.assertEqual([r.index for r in inputs.routes_for("")], [8, 7, 12, 4])
        self.assertEqual([r.index for r in inputs.routes_for("mapper")], [8, 7])
        self.assertEqual(inputs.migrate("mapper", ""), ("", "MME"))
        self.assertEqual(inputs.migrate("mme", ""), ("endpoint-realtek", "MME"))
        self.assertEqual(inputs.migrate("endpoint-realtek", ""), ("endpoint-realtek", ""))
        self.assertEqual([r.index for r in inputs.routes_for("endpoint-realtek", interface=BACKENDS[2])], [12])
        self.assertEqual([r.index for r in inputs.routes_for("", preferred=BACKENDS[2])], [12, 8, 7, 4])

    def test_interfaces_depend_on_the_selected_device(self):
        asio = Route(15, "Interfaz USB", "ASIO", 48000, 2, "usb-asio")
        inputs = group_routes([WASAPI, MME, DIRECT, MAPPER, asio])
        self.assertEqual(inputs.interfaces_for("endpoint-realtek"), set(BACKENDS[:3]))
        self.assertEqual(inputs.interfaces_for("usb-asio"), {"ASIO"})
        self.assertNotIn("ASIO", inputs.interfaces_for(""))
        self.assertEqual(inputs.interfaces_for("missing"), set())

    def test_ambiguous_names_are_retained_as_separate_devices(self):
        second = replace(WASAPI, index=6, endpoint="other", legacy_key="other")
        inputs = group_routes([WASAPI, second, MME])
        self.assertEqual(len(inputs.devices), 3)
        self.assertEqual(len({item.label for item in inputs.devices}), 3)
        self.assertEqual([r.index for r in inputs.routes_for("other")], [6])

    def test_default_endpoint_override_and_explicit_device_are_distinct(self):
        usb = replace(WASAPI, index=5, name="USB", endpoint="usb", default=False)
        inputs = group_routes([WASAPI, usb, MAPPER])
        self.assertEqual([r.index for r in inputs.routes_for("", "usb")], [8, 5])
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
        self.assertEqual(driver.tried, [(4, 16000, 1), (4, 16000, 2), (4, 48000, 1), (4, 48000, 2)])
        self.assertEqual(len(pcm), 1600)
        self.assertGreater(capture.level, 0)

    def test_silent_wasapi_switches_to_mme_mapper(self):
        self.enterContext(patch("audio_input.DIGITAL_SILENCE", 0.05))
        driver = FakeSoundDevice([(4, 48000, 1), (8, 44100, 1)], {4: 0, 8: 500})
        self.enterContext(patch("audio_input.AUTO_ORDER", BACKENDS))
        capture = self.input(driver, "endpoint-realtek")
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


    def test_wasapi_uses_the_shared_mix_and_retries_a_format_without_words(self):
        from struct import pack

        from windows_audio import decode_mix_format

        data = pack("<HHIIHHHHI", 0xfffe, 2, 48000, 384000, 8, 32, 22, 32, 3)
        data += bytes.fromhex("0300000000001000800000aa00389b71")
        self.assertEqual(decode_mix_format(data), (48000, 2, "float32"))
        route = replace(WASAPI, mix=decode_mix_format(data))
        self.assertEqual(next(iter(input_formats(route))), AudioFormat(48000, 2, dtype="float32"))
        driver = FakeSoundDevice([(4, 48000, 2)], {4: 500})
        self.enterContext(patch("audio_input.portaudio", return_value=nullcontext(driver)))
        self.enterContext(patch("audio_input.sys", Mock(platform="fixture")))
        rejected = set()
        inputs = group_routes([route])
        with capture_input(inputs, "endpoint-realtek", Event(), interface=BACKENDS[0]) as capture:
            self.assertEqual(capture.format.dtype, "float32")
            reject_recognition(capture, rejected)
        self.assertNotIn(4, rejected)
        with capture_input(inputs, "endpoint-realtek", Event(), rejected, interface=BACKENDS[0]) as capture:
            self.assertEqual(capture.format.dtype, "int16")
            self.assertGreater(capture.level, 0)

    def test_disconnected_saved_interface_recovers_on_the_same_device(self):
        driver = FakeSoundDevice([(7, 16000, 1)], {7: 500})
        self.enterContext(patch("audio_input.portaudio", return_value=nullcontext(driver)))
        self.enterContext(patch("audio_input.sys", Mock(platform="fixture")))
        with capture_input(group_routes([WASAPI, MME]), "endpoint-realtek", Event(),
                           interface="ASIO", recover_interface=True) as capture:
            self.assertEqual(capture.route.index, 7)
            self.assertIn("ASIO no está disponible", capture.notice)
            self.assertTrue(capture.automatic)

    def test_192khz_format_comes_after_voice_rates_and_filters_aliases(self):
        import audioop
        from math import pi, sin

        from audio_input import input_formats

        route = replace(WASAPI, rate=192000)
        formats = list(input_formats(route))
        self.assertEqual(formats[0].rate, 16000)
        self.assertGreater(next(i for i, fmt in enumerate(formats) if fmt.rate == 192000), 3)
        signal = array("h", (round(15000 * sin(2 * pi * 31000 * i / 192000))
                             for i in range(19200))).tobytes()
        converter = PcmConverter(AudioFormat(192000, 1))
        restored = b"".join(converter.convert(signal[i:i + 3900]) for i in range(0, len(signal), 3900))
        old, _ = audioop.ratecv(signal, 2, 1, 192000, 16000, None)
        self.assertEqual(len(restored), len(old))
        self.assertGreater(audioop.rms(old, 2), 10000)
        self.assertLess(audioop.rms(restored[160:], 2), 30)

    def test_44100_conversion_preserves_state_across_uneven_blocks(self):
        raw = array("h", ((i % 137) * 100 - 6500 for i in range(4410))).tobytes()
        fmt = AudioFormat(44100, 1)
        single = PcmConverter(fmt).convert(raw)
        split = PcmConverter(fmt)
        self.assertEqual(single, b"".join(split.convert(raw[i:i + 466]) for i in range(0, len(raw), 466)))
        self.assertEqual(len(single), 3200)


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
        from voice_recognition import MicRecognition

        root = tk.Tk()
        test, cancel = Mock(), Mock()
        dialog = VoiceDialog(root, VoiceSettings(), Mock(), Mock(), test, cancel,
                             lambda: (65, "Realtek · WASAPI · 48000 Hz"),
                             lambda: MicRecognition(True, True, "abre Spotify", True))
        try:
            root.update()
            self.assertEqual(float(dialog.level["value"]), 65)
            self.assertIn("48000 Hz", dialog.input_route["text"])
            inputs = group_routes([WASAPI, MME, DIRECT])
            dialog.show_catalog(inputs, [], "")
            dialog.microphone.set(inputs.devices[0].label)
            dialog.update_interfaces()
            self.assertNotIn("ASIO", dialog.interface["values"])
            dialog.interface.set("DirectSound")
            dialog.test_button.invoke()
            test.assert_called_once_with(WASAPI.endpoint, BACKENDS[2])
            self.assertIn("Palabras reconocidas", dialog.test_status["text"])
            self.assertEqual(dialog.transcription["text"], "abre Spotify")
            self.assertIn("disabled", str(dialog.test_button["state"]))
            dialog.test_result("Señal recibida")
            self.assertEqual(str(dialog.test_button["state"]), "normal")
        finally:
            root.destroy()
        cancel.assert_called_once()
