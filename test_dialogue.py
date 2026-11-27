from collections import deque
from concurrent.futures import Future
from queue import SimpleQueue
from threading import Event
import unittest
from unittest.mock import Mock, patch

from commands import HELP, parse
from dialogue import Clarification, Dialogue, SelectedCommand, TargetOption, split_speech
from jarvis import Desktop, execute
from preferences import VoiceSettings
from resident import Resident
from speech_cancel import SpeechCancellation
from voice_recognition import Conversation, Transcript
from voice_service import VoiceService


class DialogueTest(unittest.TestCase):
    def test_help_supports_topic_examples_repeat_and_finish(self):
        dialogue = Dialogue()
        self.assertEqual(dialogue.turn("ayuda", 0).command, "ayuda")
        first = dialogue.answer("ayuda", HELP)
        self.assertIn("¿Sobre qué", first.speech)
        windows = dialogue.turn("ventanas", 1)
        self.assertIn("minimizar", windows.speech)
        self.assertIn("¿Quieres un ejemplo?", windows.speech)
        example = dialogue.turn("sí", 2)
        self.assertIn("mueve Firefox", example.speech)
        self.assertEqual(dialogue.turn("repite", 3).speech, example.speech)
        self.assertIn("izquierda", dialogue.turn("dame más detalles", 4).speech)
        self.assertTrue(dialogue.turn("no", 5).end)
        self.assertIn("Todavía", dialogue.turn("repite", 6).speech)

    def test_long_non_help_replies_are_paginated_and_detail_changes_slice(self):
        apps = "\n".join(f"Aplicación {n}" for n in range(1, 13))
        short = Dialogue("breve")
        first = short.answer("aplicaciones", apps)
        self.assertIn("Encontré 12 aplicaciones", first.speech)
        self.assertNotIn("Aplicación 3", first.speech)
        page = short.turn("continúa", 1)
        self.assertIn("Aplicación 3", page.speech)
        self.assertIn("Aplicación 4", page.speech)
        longer = Dialogue("ampliado")
        self.assertIn("Aplicación 5", longer.answer("aplicaciones", apps).speech)
        self.assertTrue(all(len(part) <= 145 for part in split_speech(apps)))
        self.assertIn("de 1920 por 1080", longer.answer("pantallas", "1: (0, 0, 1920, 1080) (principal)").speech)

    def test_clarification_uses_a_snapshot_and_never_picks_from_yes(self):
        desktop = Desktop.__new__(Desktop)
        desktop.api = Mock()
        items = [(1, "Correo - Firefox", "firefox"), (2, "Noticias - Firefox", "firefox")]
        desktop.windows = lambda: items
        result = execute(desktop, "cierra Firefox", conversational=True)
        self.assertIsInstance(result, Clarification)
        self.assertIn("varias", execute(desktop, "cierra Firefox"))
        dialogue = Dialogue()
        first = dialogue.answer("cierra Firefox", result)
        self.assertIn("Opción 2", first.speech)
        self.assertIsNone(dialogue.turn("sí", 1).command)
        selected = dialogue.turn("la segunda", 2).command
        self.assertIsInstance(selected, SelectedCommand)
        self.assertIn("Solicité cerrar", execute(desktop, selected.command, True, selected.option.target))
        desktop.api.PostMessageW.assert_called_once_with(2, 0x10, 0, 0)
        items.pop()
        self.assertIn("ha cambiado", execute(desktop, selected.command, True, selected.option.target))
        desktop.api.PostMessageW.assert_called_once()

    def test_application_choice_is_resolved_by_name_and_revalidated(self):
        desktop = Desktop.__new__(Desktop)
        desktop.applications = lambda: [("Edición de música", "MusicId"), ("Edición de fotos", "PhotoId")]
        result = execute(desktop, "abre edición", conversational=True)
        self.assertIn("varias aplicaciones", execute(desktop, "abre edición"))
        dialogue = Dialogue()
        dialogue.answer("abre edición", result)
        choice = dialogue.turn("fotos", 2).command
        with patch("jarvis.os.startfile", create=True) as launch:
            execute(desktop, choice.command, conversational=True, selection=choice.option.target)
        launch.assert_called_once_with(r"shell:AppsFolder\PhotoId")

    def test_expiry_and_cancel_remove_pending_actions(self):
        question = Clarification("Ambigua", (TargetOption("Una", (1,)),), "ventanas")
        dialogue = Dialogue()
        dialogue.answer("cierra Firefox", question)
        dialogue.keep(1, 5)
        self.assertIsNone(dialogue.turn("uno", 6).command)
        dialogue.answer("cierra Firefox", question)
        self.assertTrue(dialogue.turn("cancela", 7).end)
        self.assertIsNone(dialogue.turn("uno", 8).command)
        dialogue.answer("cierra Firefox", question)
        dialogue.abandon_question()
        self.assertIsNone(dialogue.turn("uno", 9).command)

    def test_single_turn_speech_still_answers_without_a_panel(self):
        dialogue = Dialogue(enabled=False)
        self.assertIn("controlar monitores", dialogue.answer("ayuda", HELP).speech)
        text = dialogue.answer("aplicaciones", "Una\nDos\nTres\nCuatro").speech
        self.assertIn("Encontré 4", text)
        self.assertNotIn("¿Quieres", text)
        self.assertEqual(parse("mueve Firefox al monitor dos"), ("place", "firefox", "monitor", 2))


class PlaybackTest(unittest.TestCase):
    def test_only_explicit_high_confidence_stop_can_interrupt(self):
        capture = Mock()
        capture.read.side_effect = [b"orden", None, b"duda", None, b"stop"]
        with patch("speech_cancel.SpanishRecognizer") as factory:
            factory.return_value.feed.side_effect = [
                Transcript("cierra spotify", 0.99), Transcript("jarvis para", 0.54),
                Transcript("jarvis para", 0.95),
            ]
            stopped = Event()
            token = SpeechCancellation(Event(), stopped, capture, model=object())
            self.assertFalse(token.is_set())
            self.assertFalse(token.is_set())
            self.assertTrue(token.is_set())
            self.assertTrue(stopped.is_set())
        self.assertIn("[unk]", factory.call_args.args[1])

    def test_tray_stop_cancels_remaining_speech_segments(self):
        service = VoiceService(Mock(), Mock(), Mock())
        spoken = []

        def play(text, _settings, token):
            spoken.append(text)
            service.stop_speech()
            self.assertTrue(token.is_set())

        with patch("voice_service.speak", side_effect=play):
            _, interrupted = service.play("Texto " * 70, VoiceSettings())
        self.assertTrue(interrupted)
        self.assertEqual(len(spoken), 1)
        service.submit.assert_not_called()

    def test_playback_of_the_activation_word_cannot_arm_interruption(self):
        service = VoiceService(Mock(), Mock(), Mock())
        service.model = object()
        capture = Mock()
        with (patch("speech_cancel.SpanishRecognizer") as factory,
              patch("voice_service.speak") as speak):
            service.play("El asistente se llama Jarvis.", VoiceSettings(), capture)
        factory.assert_not_called()
        capture.resume.assert_not_called()
        self.assertTrue(speak.called)


class VoiceIntegrationTest(unittest.TestCase):
    def test_followup_accepts_audio_without_wake_until_deadline(self):
        detector = Mock()
        recognizer = Mock(feed=Mock(return_value=Transcript("ventanas", 0.93)))
        exchange = Conversation(detector, lambda: recognizer, Mock())
        exchange.listen_for_reply(1, 5)
        self.assertEqual(exchange.feed(b"audio", 2).text, "ventanas")
        detector.feed.assert_not_called()
        self.assertIsNone(exchange.feed(b"expired", 6))
        self.assertFalse(exchange.following)

    def test_help_followup_is_spoken_without_dispatching_a_window_list(self):
        answer = Future()
        answer.set_result(HELP)
        service = VoiceService(Mock(return_value=answer), Mock(), Mock())
        capture = Mock(level=22, label="simulada", notice="")
        detector = Mock(feed=Mock(return_value=b"tail"))
        recognizers = [
            Mock(feed=Mock(return_value=Transcript("ayuda", 0.99))),
            Mock(feed=Mock(return_value=Transcript("ventanas", 0.95))),
            Mock(),
        ]

        def read():
            if capture.read.call_count <= 2:
                return b"audio"
            service.changed.set()
            return None

        capture.read.side_effect = read
        with (patch.object(service, "recognize", side_effect=recognizers),
              patch("voice_service.speak") as speak,
              patch("voice_service.PLAYBACK_GUARD_SECONDS", 0)):
            service.listen(capture, detector, VoiceSettings())
        service.submit.assert_called_once_with("ayuda")
        self.assertEqual(detector.feed.call_count, 1)
        all_speech = " ".join(call.args[0] for call in speak.call_args_list)
        self.assertIn("¿Sobre qué necesitas ayuda?", all_speech)
        self.assertIn("Puedes mover, cerrar", all_speech)

    def test_hidden_resident_delivers_clarification_asynchronously(self):
        resident = Resident.__new__(Resident)
        resident.closing = resident.installing = False
        resident.panel = None
        resident.microphone = True
        resident.voice_options = VoiceSettings(enabled=True)
        resident.voice_log = deque(maxlen=24)
        resident.events = SimpleQueue()
        resident.assistant = Mock()
        resident.show = Mock()
        reply = Future()
        output = Clarification("Hay varias ventanas.", (TargetOption("Una", (1,)),), "ventanas")
        reply.set_result(output)
        resident.assistant.submit_voice.return_value = reply
        pending = resident.request_voice("cierra Firefox")
        resident.deliver()
        self.assertIs(pending.result(), output)
        self.assertIn(("Hay varias ventanas.", "reply"), resident.voice_log)
        resident.show.assert_not_called()
