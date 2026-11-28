from concurrent.futures import Future
from io import BytesIO
from pathlib import PureWindowsPath
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch

from app_catalog import Application, Identity
from app_launch import Running
from audio_input import CaptureError, Inputs, Route
from call_audio import PlaybackActivity, contaminated, playback_input
from commands import parse
from command_language import normalize_order
from dialogue import Clarification, Dialogue, SelectedCommand, TargetOption
from game_providers import game_app, hoyoplay_games
from lifecycle import LifecycleMonitor, LifecycleSettings, close_verdict
from preferences import VoiceSettings
from resident import Resident
from updater import install_update, release_policy, select_update, version_tuple
from voice_context import ContextOrder
from voice_recognition import Transcript
from voice_service import VoiceService
import json


ASSET = {"name": "JARVIS.exe", "size": 50, "digest": "sha256:" + "a" * 64}


def candidate(version, experimental=False):
    return {"tag_name": "v" + version, "prerelease": experimental, "assets": [ASSET]}


class UpdateChannels(TestCase):
    def test_stable_experimental_and_explicit_return(self):
        releases = [candidate("0.6.4.1"), candidate("0.6.4.2"), candidate("0.6.5-rc.4", True),
                    candidate("0.6.6-beta.1", True), candidate("0.6.7-alpha.1", True)]
        policy = {version_tuple("0.6.4.2"): {"channel": "experimental"},
                  version_tuple("0.6.7-alpha.1"): {"status": "defectuosa"},
                  version_tuple("0.6.6-beta.1"): {"status": "retirada"}}
        self.assertIsNone(select_update(releases, "stable", policy, "0.6.5-rc.3"))
        self.assertEqual(select_update(releases, "stable", policy, "0.6.5-rc.3", True)[0], "v0.6.4.1")
        self.assertEqual(select_update(releases, "experimental", policy, "0.6.5-rc.3")[0], "v0.6.5-rc.4")
        self.assertIsNone(select_update([candidate("0.6.8-rc.1")], "experimental", policy, "0.6.5-rc.3"))

    def test_registry_cannot_unblock_known_failures_and_install_rechecks(self):
        current = {"schema": 1, "versions": {"0.6.5-rc.1": {"channel": "experimental", "status": "estable"}}}
        with patch("updater.urlopen", return_value=BytesIO(json.dumps(current).encode())):
            self.assertEqual(release_policy(remote=True)[version_tuple("0.6.5-rc.1")]["status"], "defectuosa")
        with (patch("updater.release_policy", return_value={version_tuple("0.6.5-rc.4"): {"status": "retirada"}}),
              patch("updater.urlopen") as network):
            with self.assertRaisesRegex(ValueError, "bloqueada"):
                install_update(("v0.6.5-rc.4", "a" * 64, 30), check_policy=True)
            network.assert_not_called()

    def test_missing_or_invalid_setting_defaults_to_stable(self):
        from preferences import update_channel
        with patch("preferences.read_value", return_value="obsolete"):
            self.assertEqual(update_channel(), "stable")
        with patch("preferences.read_value", return_value="experimental"):
            self.assertEqual(update_channel(), "experimental")


class CallsAndHistory(TestCase):
    def test_playback_level_signals_overlap_without_authorizing_voice(self):
        playback = PlaybackActivity(Mock(side_effect=[0.008, 0.11, 0.09]))
        for now in (0.0, 0.16, 0.32):
            playback.observe(now)
        self.assertTrue(playback.overlapped(0.33))
        self.assertFalse(playback.overlapped(2.0))
        weak = Transcript("cierra pulcro", 0.89, words=(("pulcro", 0.2, 0.9, 0.43),))
        clean = Transcript("abre chrome", 0.9, words=(("chrome", 0.3, 0.8, 0.9),))
        self.assertTrue(contaminated(weak, True))
        self.assertFalse(contaminated(clean, True))
        self.assertFalse(contaminated(weak, False))
        self.assertTrue(playback_input("Mezcla estéreo (Realtek)"))
        self.assertFalse(playback_input("Micrófono de auriculares USB"))
        mapper = Route(2, "Sound mapper", "MME", 16000, 1, "X", mapper=True)
        with self.assertRaisesRegex(CaptureError, "mezcla de reproducción"):
            Inputs((), (mapper,), frozenset({"loop"})).routes_for("", "loop")

    def test_history_keeps_the_real_answer_separate_from_game_name(self):
        desktop = Resident.__new__(Resident)
        desktop.can_use_voice = Mock(return_value=True)
        desktop.revision = 0
        desktop.pending_approval = None
        desktop.record_voice = Mock()
        desktop.run_voice_action = Mock()
        done = Future()
        done.set_result("Solicité el arranque.")
        submit = Mock(return_value=done)
        service = VoiceService(submit, Mock(), Mock())
        dialogue = Dialogue()
        order = ContextOrder("abre john cae start reading", ("Honkai Star Rail",), "abre john cae start reading")
        option = TargetOption("Honkai Star Rail", ("ID",))
        dialogue.answer(order, Clarification("Una coincidencia", (option,), "aplicaciones"))
        service.interpret(Transcript("Sí", 0.97), dialogue, VoiceSettings(), 1.0, "owner")
        selected = submit.call_args.args[0]
        self.assertIsInstance(selected, SelectedCommand)
        self.assertEqual(selected.heard, "Sí")
        desktop.dispatch_voice(selected, "owner", Future())
        self.assertEqual([item.args for item in desktop.record_voice.call_args_list],
                         [("VOZ · Sí", "you"), ("Destino confirmado: Honkai Star Rail.", "reply")])
        desktop.run_voice_action.assert_called_once()


class GameLifecycle(TestCase):
    def setUp(self):
        self.game = game_app("Stellar Race", "epic", Identity("uri", "one"), r"D:\Games\Stellar")
        self.other = game_app("Another Game", "epic", Identity("uri", "two"), r"D:\Games\Other")
        path = r"C:\Epic\EpicGamesLauncher.exe"
        self.registration = Application("Epic Games", "registry", Identity("file", path), (Identity("exe", path),))
        self.main = Running(10, r"D:\Games\Stellar\play.exe", window=11, started=22)
        self.launcher = Running(15, path, window=50, started=29)

    def test_hoyoplay_uses_registered_launcher_without_losing_product_identity(self):
        snapshot = {"Start": [{"Name": "HoYoPlay", "AppID": "HoYoPlay.Application"}]}
        first = game_app("Star Rail", "hoyoplay", Identity("unavailable", "d"), r"D:\Hoyo\StarRail")
        second = game_app("Genshin Impact", "hoyoplay", Identity("unavailable", "e"), r"E:\Hoyo\Genshin")
        with patch("game_providers.publisher_games", return_value=(first, second)):
            result = tuple(hoyoplay_games(snapshot, (), ()))
        self.assertEqual(result[0].route.kind, "provider_client")
        self.assertNotEqual(result[0].key, result[1].key)
        self.assertIn("pulsa Jugar", result[1].note)

    def test_intents_and_exceptions(self):
        self.assertEqual(parse("cierra stellar race y su launcher"), ("close", "stellar race", "associated"))
        self.assertEqual(parse(normalize_order("cierra stellar race, pero deja epic abierto")),
                         ("close", "stellar race", "keep"))
        self.assertFalse(LifecycleSettings(True, ("epic",)).allows(self.game, True))
        self.assertFalse(LifecycleSettings(True, games=("stellar race",)).allows(self.game))
        self.assertTrue(LifecycleSettings().allows(self.game, True))

    def test_dependency_and_operations_leave_launcher_open(self):
        all_apps = (self.game, self.other, self.registration)
        second = Running(18, r"D:\Games\Other\main.exe", window=20, started=29)
        self.assertEqual(close_verdict(self.game, [self.launcher, second], all_apps, self.launcher, Mock(), False),
                         "dependent")
        for status in ("busy", "unknown", "idle"):
            self.assertEqual(close_verdict(self.game, [self.launcher], all_apps, self.launcher,
                                           lambda *_: status, False), status)
        self.assertEqual(close_verdict(self.game, [self.launcher], all_apps, self.launcher, Mock(), True), "active")

    def test_graceful_async_closure_when_provider_proves_idle(self):
        report, close = Mock(), Mock(return_value=True)
        session = iter(((self.main,), (), (), (self.launcher,), (self.launcher,), ()))
        worker = LifecycleMonitor(lambda: next(session), close, report, Mock(return_value=False),
                                  activity=lambda *_: "idle")
        seconds = [0.0]
        def wait(interval):
            seconds[0] += interval
            return False
        try:
            worker.track(self.game, self.main, (self.game, self.registration), True, None,
                         lambda: seconds[0], wait)
        finally:
            worker.close()
        close.assert_called_once_with(self.launcher)
        self.assertGreaterEqual(seconds[0], 1.5)
        self.assertIn("se cerró", report.call_args.args[0])
