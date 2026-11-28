from concurrent.futures import Future
from io import BytesIO
import json
from unittest import TestCase
from unittest.mock import Mock, patch

from benchmark_voice import CASES, benchmark
from biometric_audio import Reason
from biometric_audio import Reading
from command_language import normalize_order
from commands import parse
from dialogue import Clarification, Dialogue
from jarvis import Desktop, execute
from permissions import SecurityPolicy
from preferences import VoiceSettings, adaptation_settings
from test_voice import PROFILE, SAMPLE
from updater import latest_update, version_tuple
from voice_recognition import Conversation, Transcript
from voice_service import VoiceService
from voice_adaptation import Adaptation


class IntentTest(TestCase):
    def test_lexical_variations_preserve_meaning(self):
        orders = {
            ("close", "spotify"): ("Cierra Spotify", "Cerrar Spotify", "Ciérrame Spotify", "Cerrá Spotify",
                                  "Cerraré Spotify", "Quítame el Spotify"),
            ("open", "calculadora"): ("Ábreme la calculadora", "Ponme la calculadora", "Abre la calculadora de Windows",
                                      "Porfa, abre cálculo", "¿Puedes abrir la calculadora?"),
            ("system", "restart"): ("Reiníciame el ordenador", "Reinicia el PC", "Reinicia la compu"),
            ("place", "vscode", "left", None): ("Pon el VSCode a la izquierda",),
            ("place", "visual studio code", "top_right", None): ("Mueve Visual Studio Code a la esquina superior derecha",),
        }
        for expected, phrases in orders.items():
            for phrase in phrases:
                self.assertEqual(parse(normalize_order(phrase)), expected, phrase)

    def test_conversation_and_hypothetical_actions_are_blocked(self):
        for phrase in ('No cierres Spotify', 'Si reinicia el PC', 'Cierra Spotify si quieres',
                       '¿Cierra Spotify?', '«Cierra Spotify»', 'Cierra Spotify y luego reinicia el PC',
                       'Dijo que cierra Spotify', 'Cierra Spotify, por ejemplo'):
            self.assertIsNone(parse(normalize_order(phrase)), phrase)
        self.assertIsNone(parse(normalize_order("Reinisea el PC")))

    def test_identical_application_identity_does_not_create_an_option(self):
        desktop = Desktop.__new__(Desktop)
        desktop.applications = lambda: [("Spotify", "AppId"), ("Spotify", "appid")]
        policy = SecurityPolicy("Libertad")
        with patch("jarvis.os.startfile", create=True) as launch:
            result = execute(desktop, "abre spotify", conversational=True, policy=policy)
            self.assertIsInstance(result, str)
            launch.assert_called_once()
            desktop.applications = lambda: [("Spotify", "SpotifyId"), ("Spotify", "OtherId")]
            result = execute(desktop, "abre spotify", conversational=True, policy=policy)
            self.assertIsInstance(result, Clarification)
            self.assertEqual(len(result.options), 2)
            launch.assert_called_once()

    def test_personal_aliases_are_explicit_editable_and_action_neutral(self):
        settings = Adaptation(True, (("es potify", "Spotify"), ("bi es coude", "Visual Studio Code")))
        self.assertEqual(settings.apply(normalize_order("abre es potify")), "abre spotify")
        self.assertEqual(settings.apply(normalize_order("cierra es potify")), "cierra spotify")
        self.assertEqual(settings.apply(normalize_order("mueve bi es coude a la izquierda")),
                         "mueve visual studio code a la izquierda")
        self.assertEqual(settings.apply("reinicia el equipo"), "reinicia el equipo")
        self.assertEqual(Adaptation(False, settings.aliases).apply("abre es potify"), "abre es potify")
        with self.assertRaises(ValueError):
            Adaptation(True, (("  ", "Spotify"),))
        with self.assertRaises(ValueError):
            Adaptation(True, (("prueba", "no abras Chrome"),))
        with patch("preferences.read_value", return_value='{"enabled":true,"aliases":[["es potify","Spotify"]]}'):
            self.assertEqual(adaptation_settings().apply("abre es potify"), "abre spotify")
        self.assertTrue(settings.enabled)


class AuthorizationTest(TestCase):
    def test_speaker_pcm_is_limited_to_recognized_word_range(self):
        exchange = Conversation(Mock(), Mock(), Mock())
        first = b"\x01\x00" * 16000
        second = b"\x02\x00" * 16000
        exchange.audio[:] = first + second
        exchange.boundary = 8000
        exchange.activation = first[:8000]
        result = Transcript("cierra spotify", 0.93, words=(("cierra", 1.15, 1.4, .92), ("spotify", 1.4, 1.8, .94)))
        pcm, prefix = exchange.speaker_audio(result)
        self.assertEqual(set(pcm), {0, 2})
        self.assertEqual(prefix, b"")

    def test_high_risk_intent_requires_word_confidence_and_no_prefix_borrowing(self):
        service = VoiceService(Mock(), Mock(), Mock())
        text = "reinicia el equipo"
        weak = Transcript(text, .90, words=(("reinicia", 0.1, .8, .44),))
        result = service.interpret(weak, Dialogue(), VoiceSettings(enabled=True), 0, PROFILE.id)
        self.assertFalse(result.accepted)
        service.submit.assert_not_called()
        service.recent_stages.clear()

        service.profiles = (PROFILE,)
        capture = Mock(level=30, label="simulada", notice="")

        def read():
            if capture.read.call_count == 1:
                return b"pcm"
            service.changed.set()
            return None

        capture.read.side_effect = read
        detector = Mock(feed=Mock(return_value=b"order"), activation=b"owner prefix", boundary=0)
        decoder = Mock(feed=Mock(return_value=Transcript(text, .95)))
        reply = Future()
        reply.set_result("Enviada")
        service.submit.return_value = reply
        with (patch.object(service, "recognize", return_value=decoder),
              patch.object(service, "sample", return_value=Reading(None, sample=SAMPLE)),
              patch.object(service, "play", return_value=("", False)),
              patch("voice_service.verify", return_value=(Reason.ACCEPTED, PROFILE.id)) as verify,
              patch("voice_service.PLAYBACK_GUARD_SECONDS", 0)):
            service.listen(capture, detector, VoiceSettings(enabled=True))
        self.assertEqual(verify.call_args.args[1:3], (b"order", b""))
        self.assertEqual([event["fase"] for event in service.recent_stages],
                         ["audio", "activación", "transcripción", "hablante", "intención"])
        self.assertNotIn("owner prefix", json.dumps(list(service.recent_stages)))


class RecognitionCorpusTest(TestCase):
    def test_release_corpus_has_intended_and_negative_cases(self):
        from voice_recognition import MODEL_PATH

        if not MODEL_PATH.is_dir():
            self.skipTest("Modelo local ausente")
        result = benchmark(".", None)
        for name in ("help", "calc", "quick", "latin-help", "separated", "negcalc", "prefix", "other"):
            self.assertEqual(result["cases"][name]["intent"], CASES[name], name)
        for name in ("prefix", "other"):
            self.assertFalse(result["cases"][name]["activated"], name)


class VersionTest(TestCase):
    def test_semantic_order_and_channel_choice(self):
        values = ("0.6.4", "0.6.4.1", "0.6.4.2", "0.6.10", "1.0.0-alpha.1", "1.0.0-beta.2",
                  "1.0.0-Beta.10", "1.0.0-RC.1", "1.0.0", "2.0.0")
        self.assertEqual(tuple(sorted(values, key=version_tuple)), values)
        for bad in ("1.0", "1.0.0.0.1", "1.0.0-beta.0", "1.0.0../bad", "1.0.0-dev"):
            with self.assertRaises(ValueError):
                version_tuple(bad)

        asset = [{"name": "JARVIS.exe", "size": 100, "digest": "sha256:" + "b" * 64}]
        versions = [dict(tag_name="v0.7.0-beta.1", prerelease=True, assets=asset),
                    dict(tag_name="v0.7.0-rc.1", prerelease=True, assets=asset),
                    dict(tag_name="v0.7.0", draft=True, assets=asset),
                    dict(tag_name="v0.6.5", assets=asset),
                    dict(tag_name="v0.9.0-alpha.1", prerelease=True, assets=asset)]
        for channel, expected in (("stable", "v0.6.5"), ("beta", "v0.7.0-rc.1"),
                                  ("development", "v0.9.0-alpha.1")):
            with patch("updater.urlopen", return_value=BytesIO(json.dumps(versions).encode())):
                self.assertEqual(latest_update(channel)[0], expected)
