from concurrent.futures import Future
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from preferences import VoiceSettings
from voice_recognition import MODEL_PATH, TIMEOUT, Conversation, Transcript
from voice_service import VoiceService


class ConversationTest(unittest.TestCase):
    def test_wake_preserves_the_following_audio_and_can_time_out(self):
        detector = Mock()
        detector.feed.side_effect = [None, b"tail", None]
        recognizer = Mock()
        recognizer.feed.return_value = None
        states = Mock()
        conversation = Conversation(detector, lambda: recognizer, states)
        self.assertIsNone(conversation.feed(b"no wake", 0))
        recognizer.feed.assert_not_called()
        self.assertIsNone(conversation.feed(b"wake", 1))
        recognizer.feed.assert_called_once_with(b"tail")
        self.assertIsNone(conversation.feed(b"too late", 1 + TIMEOUT))
        self.assertIsNone(conversation.active)
        detector.reset.assert_called_once()
        self.assertIsNone(conversation.feed(b"command without wake", 8))
        self.assertEqual([call.args for call in states.call_args_list], [("listening",), ("waiting",)])


class VoiceServiceTest(unittest.TestCase):
    def test_ambient_audio_is_discarded_while_reply_is_spoken(self):
        reply = Future()
        reply.set_result("Abrí Spotify.")
        on_state = Mock()
        service = VoiceService(Mock(return_value=reply), on_state, Mock())
        settings = VoiceSettings(enabled=True)
        capture = Mock()
        detector = Mock()
        detector.feed.return_value = b"tail"
        recognizer = Mock()
        recognizer.feed.return_value = Transcript("abre spotify", 0.96)

        def read():
            if capture.read.call_count == 1:
                return b"audio"
            service.changed.set()
            return None

        capture.read.side_effect = read

        def playback(*args):
            capture.pause.assert_called_once()
            capture.resume.assert_not_called()
            self.assertEqual(capture.read.call_count, 1)

        with (patch.object(service, "recognize", return_value=recognizer),
              patch("voice_service.speak", side_effect=playback),
              patch("voice_service.PLAYBACK_GUARD_SECONDS", 0)):
            service.listen(capture, detector, settings)

        service.submit.assert_called_once_with("abre spotify")
        capture.resume.assert_called_once()
        detector.reset.assert_called_once()
        self.assertEqual([call.args[0] for call in on_state.call_args_list],
                         ["waiting", "listening", "processing", "executing", "speaking", "waiting"])

    def test_low_confidence_and_muting_do_not_send_commands(self):
        service = VoiceService(Mock(), Mock(), Mock())
        service.configure(VoiceSettings(enabled=True), microphone=False)
        self.assertIsNone(service.thread)
        service.on_state.assert_called_once_with("muted", "")
        with patch("voice_service.speak") as speak:
            service.changed.clear()
            service.respond(Transcript("cierra Spotify", 0.31), VoiceSettings(enabled=True))
        service.submit.assert_not_called()
        speak.assert_called_once()

    def test_disconnect_retries_and_restores_capture(self):
        waiting, disconnected = Event(), Event()

        def state_change(state, _detail):
            if state == "unavailable":
                disconnected.set()
            if state == "waiting" and disconnected.is_set():
                waiting.set()

        service = VoiceService(Mock(), state_change, Mock())
        capture = Mock()
        def read():
            service.changed.wait(0.02)
            return None

        capture.read.side_effect = read
        microphone = Mock()
        microphone.__enter__ = Mock(return_value=capture)
        microphone.__exit__ = Mock(return_value=False)
        with (patch("voice_service.input_devices", return_value=[]),
              patch("voice_service.Microphone", side_effect=[OSError("desconectado"), microphone]),
              patch("voice_service.WakeDetector", return_value=Mock(feed=Mock(return_value=None))),
              patch("voice_service.RETRY_SECONDS", 0.01)):
            try:
                service.configure(VoiceSettings(enabled=True), microphone=True)
                self.assertTrue(waiting.wait(3))
                self.assertTrue(disconnected.is_set())
            finally:
                service.close()
        self.assertFalse(service.thread.is_alive())
        microphone.__exit__.assert_called_once()


@unittest.skipUnless((MODEL_PATH / "am" / "final.mdl").is_file(), "Requiere el modelo de voz local")
class SyntheticAudioTest(unittest.TestCase):
    def test_recognition_of_synthetic_spanish_commands(self):
        from voice_probe import test_audio

        report = test_audio(Path(__file__).with_name("tests") / "voice")
        self.assertEqual(len(report), 4)


@unittest.skipUnless(sys.platform == "win32", "Requiere el registro de Windows")
class WindowsVoicePreferencesTest(unittest.TestCase):
    def test_roundtrip_and_existing_user_defaults(self):
        import winreg

        from preferences import save_voice_settings, voice_settings

        path = fr"Software\JARVIS\VoiceTest-{uuid4().hex}"
        with patch("preferences.SETTINGS_KEY", path):
            try:
                self.assertEqual(voice_settings(), VoiceSettings())
                custom = VoiceSettings(True, "Micrófono USB", "Microsoft Helena", 45, 4)
                save_voice_settings(custom)
                self.assertEqual(voice_settings(), custom)
            finally:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
                except FileNotFoundError:
                    pass
