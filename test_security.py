from collections import deque
from concurrent.futures import Future
from pathlib import Path
from queue import SimpleQueue
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import Mock, patch
import sys
import unittest

from command_language import normalize_order, phonetic_score
from commands import parse
from dialogue import Clarification, Dialogue
from jarvis import Desktop, execute
from preferences import VoiceSettings
from resident import Resident
from speakers import Profile, VoiceSample, decode_profiles, encode_profiles, identify
from test_voice import PROFILE, SAMPLE, VECTOR
from voice_authorization import LocalApproval, PendingApproval
from voice_recognition import Transcript
from voice_service import VoiceService
from windows_protection import ProfileStore

OTHER_VECTOR = (0.0, 1.0) + (0.0,) * 126
OTHER = Profile("other", "Segunda persona", (OTHER_VECTOR,) * 3)


class SpeakerSecurityTest(unittest.TestCase):
    def test_enrollment_requires_three_matching_samples_and_roundtrips(self):
        profile = Profile.enroll("Autorizado", [SAMPLE] * 3)
        self.assertEqual(decode_profiles(encode_profiles([profile])), (profile,))
        with self.assertRaises(ValueError):
            Profile.enroll("Autorizado", [SAMPLE] * 2)
        with self.assertRaises(ValueError):
            Profile.enroll("Autorizado", [SAMPLE, SAMPLE, VoiceSample(OTHER_VECTOR, 120)])
        for raw in (b"{}", b"null", b'{"version":1,"model":"vosk-spk-0.4","profiles":[null]}'):
            with self.assertRaises(ValueError):
                decode_profiles(raw)

    def test_same_profile_is_required_for_followup_and_unknown_fails_closed(self):
        self.assertEqual(identify(SAMPLE, (PROFILE, OTHER), 0.72), PROFILE.id)
        self.assertIsNone(identify(SAMPLE, (), 0.72))
        self.assertIsNone(identify(SAMPLE, (PROFILE, OTHER), 0.72, expected=OTHER.id))
        self.assertIsNone(identify(VoiceSample(VECTOR, 10), (PROFILE,), 0.72))
        self.assertIsNone(identify(SAMPLE, (PROFILE, Profile("other", "Duplicado", (VECTOR,) * 3)), 0.72))

    def test_no_profiles_means_no_background_capture(self):
        service = VoiceService(Mock(), Mock(), Mock())
        states = []

        def notify(state, detail):
            states.append(state)
            service.stopped.set()
            service.changed.set()

        service.on_state = notify
        service.config = (VoiceSettings(enabled=True), True)
        with patch.object(service, "run_capture") as capture:
            service.run_loop()
        capture.assert_not_called()
        self.assertEqual(states, ["profiles"])

    def test_unauthorized_voice_cannot_submit_even_after_keyword(self):
        service = VoiceService(Mock(), Mock(), Mock())
        service.profiles = (PROFILE,)
        capture = Mock(level=20, label="entrada simulada", notice="")
        def read():
            if capture.read.call_count == 1:
                return bytes(1600)
            service.changed.set()
            return None
        capture.read.side_effect = read
        detector = Mock(feed=Mock(return_value=b"tail"), activation=b"")
        decoder = Mock(feed=Mock(return_value=Transcript("cierra spotify", 0.99, VoiceSample(OTHER_VECTOR, 90))))
        with patch.object(service, "recognize", return_value=decoder):
            service.listen(capture, detector, VoiceSettings(enabled=True))
        service.submit.assert_not_called()
        self.assertEqual(service.last_state[0], "voice_rejected")

    def test_different_enrolled_speaker_cannot_continue_the_previous_dialogue(self):
        service = VoiceService(Mock(), Mock(), Mock())
        service.profiles = (PROFILE, OTHER)
        answer = Future()
        answer.set_result("Prueba completada.")
        service.submit.return_value = answer
        capture = Mock(level=20, label="simulada", notice="")
        def read():
            if capture.read.call_count <= 2:
                return bytes(1600)
            service.changed.set()
            return None
        capture.read.side_effect = read
        detector = Mock(feed=Mock(return_value=b"tail"), activation=b"")
        decoders = [Mock(feed=Mock(return_value=Transcript("ayuda", 0.99, SAMPLE))),
                    Mock(feed=Mock(return_value=Transcript("cierra spotify", 0.99, VoiceSample(OTHER_VECTOR, 90))))]
        with (patch.object(service, "recognize", side_effect=decoders),
              patch("voice_service.speak"),
              patch("voice_service.PLAYBACK_GUARD_SECONDS", 0)):
            service.listen(capture, detector, VoiceSettings(enabled=True))
        service.submit.assert_called_once_with("ayuda", PROFILE.id)
        self.assertEqual(service.last_state[0], "voice_rejected")

    def test_short_wake_is_provisional_and_a_mismatched_wake_blocks_an_order(self):
        service = VoiceService(Mock(), Mock(), Mock())
        service.profiles = (PROFILE,)
        service.model = object()
        capture = Mock(level=20, label="simulada", notice="")
        def read():
            if capture.read.call_count == 1:
                return bytes(1600)
            service.changed.set()
            return None
        capture.read.side_effect = read
        detector = Mock(feed=Mock(return_value=b"tail"), activation=bytes(1600))
        decoder = Mock(feed=Mock(return_value=Transcript("abre spotify", 0.99, SAMPLE)))
        with (patch.object(service, "recognize", return_value=decoder),
              patch("voice_service.monotonic", return_value=1.0),
              patch("voice_service.wake_sample", return_value=VoiceSample(OTHER_VECTOR, 67))):
            service.listen(capture, detector, VoiceSettings(enabled=True))
        service.submit.assert_not_called()
        self.assertEqual(service.last_state, ("voice_rejected", "No se autorizó la activación."))


class ApprovalTest(unittest.TestCase):
    def resident(self):
        resident = Resident.__new__(Resident)
        resident.root = Mock()
        resident.closing = resident.installing = False
        resident.microphone = True
        resident.profiles = (PROFILE,)
        resident.voice_options = VoiceSettings(enabled=True)
        resident.pending_approval = None
        resident.assistant = Mock()
        resident.panel = None
        resident.events = SimpleQueue()
        resident.voice_log = deque()
        return resident

    def test_sensitive_execution_is_deferred_with_a_stable_window_target(self):
        desktop = Desktop.__new__(Desktop)
        desktop.windows = lambda: [(2, "Spotify", "spotify")]
        desktop.api = Mock()
        pending = execute(desktop, "cierra spotify", conversational=True, require_approval=True)
        self.assertIsInstance(pending, LocalApproval)
        desktop.api.PostMessageW.assert_not_called()
        self.assertEqual(pending.command.option.target[0], 2)
        desktop.windows = lambda: [(3, "Spotify", "spotify")]
        result = execute(desktop, pending.command.command, conversational=True,
                         selection=pending.command.option.target)
        self.assertIn("ha cambiado", result)
        desktop.api.PostMessageW.assert_not_called()

    def test_voice_yes_cannot_approve_and_local_code_is_single_use(self):
        resident = self.resident()
        local = LocalApproval("bloquea el equipo", "Bloquear Windows")
        reply = Future()
        resident.require_confirmation(local, PROFILE.id, reply)
        request = resident.pending_approval
        self.assertIsNone(Dialogue().answer("bloquea el equipo", local).command)
        self.assertIsNone(Dialogue().turn("sí", 0).command)
        resident.assistant.submit_voice.assert_not_called()
        with patch("resident.simpledialog.askstring", return_value="incorrecto"):
            resident.confirm_voice()
        resident.assistant.submit_voice.assert_not_called()
        self.assertIsNone(resident.pending_approval)
        resident.pending_approval = request
        with patch("resident.simpledialog.askstring", return_value=request.code):
            resident.confirm_voice()
        resident.assistant.submit_voice.assert_called_once()
        self.assertTrue(resident.assistant.submit_voice.call_args.kwargs["approved"])
        self.assertIsNone(resident.pending_approval)

    def test_expiry_revocation_and_muting_are_enforced(self):
        resident = self.resident()
        request = PendingApproval(LocalApproval("salir", "Salir"), PROFILE.id, "000123", monotonic() - 1)
        resident.pending_approval = request
        with (patch("resident.messagebox.showinfo"), patch("resident.simpledialog.askstring") as dialog):
            resident.confirm_voice()
        dialog.assert_not_called()
        resident.microphone = False
        pending = resident.request_voice("abre spotify", PROFILE.id)
        resident.deliver()
        self.assertTrue(pending.cancelled())
        resident.assistant.submit_voice.assert_not_called()


class LanguageTest(unittest.TestCase):
    def test_verb_variants_and_negative_language(self):
        self.assertEqual(parse(normalize_order("¿Podrías cerraré Spotify, por favor?")), ("close", "spotify"))
        self.assertEqual(parse(normalize_order("Maximizaré Firefox")), ("place", "firefox", "full", None))
        self.assertIsNone(parse(normalize_order("No cerraré Spotify")))
        self.assertIsNone(parse(normalize_order("Abre Spotify no lo cierres")))
        self.assertEqual(normalize_order("no gracias"), "no gracias")

    def test_dynamic_phonetic_candidate_is_a_clarification_only(self):
        desktop = Desktop.__new__(Desktop)
        desktop.applications = lambda: [("Rocket League", "RocketId"), ("Spotify", "SpotifyId")]
        self.assertGreater(phonetic_score("roquet lig", "Rocket League"), 0.9)
        with patch("jarvis.os.startfile", create=True) as launch:
            result = execute(desktop, "abre roquet lig", conversational=True, require_approval=True)
            self.assertIsInstance(result, Clarification)
            self.assertEqual([option.label for option in result.options], ["Rocket League"])
            launch.assert_not_called()
            dialogue = Dialogue()
            dialogue.answer("abre roquet lig", result)
            selected = dialogue.turn("opción uno", 1).command
            execute(desktop, selected.command, conversational=True, selection=selected.option.target,
                    require_approval=True)
            launch.assert_called_once_with(r"shell:AppsFolder\RocketId")


@unittest.skipUnless(sys.platform == "win32", "Requiere DPAPI de Windows")
class WindowsProfileTest(unittest.TestCase):
    def test_dpapi_authenticates_storage_and_profiles_can_be_renamed_and_removed(self):
        from dataclasses import replace

        with TemporaryDirectory() as folder:
            file = Path(folder) / "perfiles-voz.dat"
            store = ProfileStore(file)
            self.assertEqual(store.load(), ())
            profile = Profile.enroll("Persona autorizada", [SAMPLE] * 3)
            store.save((profile,))
            self.assertNotIn(b"Persona autorizada", file.read_bytes())
            self.assertEqual(store.load(), (profile,))
            store.save((replace(profile, name="Nombre nuevo"),))
            self.assertEqual(store.load()[0].name, "Nombre nuevo")
            damaged = bytearray(file.read_bytes())
            damaged[len(damaged) // 2] ^= 1
            file.write_bytes(damaged)
            with self.assertRaises((OSError, ValueError)):
                store.load()
            store.save(())
            self.assertEqual(store.load(), ())
