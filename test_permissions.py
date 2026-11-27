from concurrent.futures import Future
from io import BytesIO
import json
from unittest import TestCase
from unittest.mock import Mock, patch

from commands import parse
from dialogue import Dialogue
from jarvis import Desktop, execute
from permissions import ALLOW, BLOCK, BUTTON, CODE, HOTKEY, VERBAL, CATEGORIES, SecurityPolicy, classify
from preferences import security_settings, voice_settings
from test_security import resident_fixture
from test_voice import PROFILE
from updater import latest_update, version_tuple
from voice_authorization import ApprovalAnswer, LocalApproval, PowerAction, UNVERIFIED


class PolicyTest(TestCase):
    def test_presets_and_classification(self):
        freedom, balanced, strict = (SecurityPolicy(mode) for mode in ("Libertad", "Equilibrado", "Estricto"))
        for text in ("abre Spotify", "mueve Spotify al monitor dos", "baja volumen", "pausa musica"):
            category = classify(parse(text))
            self.assertEqual([p.method(category) for p in (freedom, balanced, strict)], [ALLOW] * 3)
        for text in ("cierra Spotify", "bloquea el equipo", "captura de pantalla", "apaga el ordenador",
                     "reinicia el equipo"):
            category = classify(parse(text))
            self.assertEqual([p.method(category) for p in (freedom, balanced, strict)], [ALLOW, VERBAL, CODE])
        self.assertEqual(classify(parse("abre terminal")), "administration")
        self.assertEqual(classify(("open", "aplicacion"), "administrador de tareas"), "administration")
        self.assertEqual(freedom.method("files"), VERBAL)
        self.assertTrue(CATEGORIES["remote"].remote)
        self.assertFalse(CATEGORIES["power"].reversible)

    def test_customization_and_critical_floor(self):
        methods = dict(open=ALLOW, close=BLOCK, screenshot=BUTTON, power=HOTKEY, lock=CODE, media=VERBAL,
                       remote=VERBAL, security=ALLOW)
        policy = SecurityPolicy("Personalizado", False, methods)
        self.assertEqual(SecurityPolicy.from_saved(policy.serialized()), policy)
        for cat, method in methods.items():
            self.assertEqual(policy.method(cat), BUTTON if cat in {"remote", "security"} else method)
        self.assertEqual(policy.method("unknown"), BLOCK)

    def test_old_preferences_migrate_without_overwriting_voice_settings(self):
        old = {"VoiceSettings": json.dumps({"enabled": True, "speaker_threshold": 78, "interface": "MME",
                                           "device": "specific-input", "volume": 50, "conversational": False})}
        with patch("preferences.read_value", side_effect=lambda _path, name, fallback: old.get(name, fallback)):
            self.assertEqual(security_settings().mode, "Estricto")
            settings = voice_settings()
            self.assertTrue(settings.enabled)
            self.assertEqual((settings.device, settings.interface, settings.speaker_threshold), ("specific-input", "MME", 78))
            self.assertFalse(settings.conversational)
            self.assertEqual(settings.volume, 50)
        with patch("preferences.read_value", side_effect=lambda _path, _name, fallback: fallback):
            self.assertEqual(security_settings().mode, "Equilibrado")
        with patch("preferences.read_value", return_value='{incompatible'):
            self.assertEqual(security_settings().method("open"), BLOCK)
            self.assertTrue(security_settings().biometrics)

    def test_policy_is_enforced_before_side_effects(self):
        desktop = Desktop.__new__(Desktop)
        desktop.api = Mock()
        desktop.windows = lambda: [(2, "Spotify", "spotify")]
        command = "cierra Spotify"
        self.assertIsInstance(execute(desktop, command, True, policy=SecurityPolicy()), LocalApproval)
        desktop.api.PostMessageW.assert_not_called()
        blocked = SecurityPolicy("Personalizado", True, {"close": BLOCK})
        self.assertIn("bloqueada", execute(desktop, command, True, policy=blocked).message)
        desktop.api.PostMessageW.assert_not_called()
        self.assertIn("Solicité", execute(desktop, command, True, policy=SecurityPolicy("Libertad")))
        desktop.api.PostMessageW.assert_called_once_with(2, 0x10, 0, 0)
        # Security settings are not a voice or console command.
        self.assertIsNone(parse("desactiva la verificación de voz"))
        self.assertIsNone(parse("cambia los permisos de jarvis"))


class ApprovalLifecycleTest(TestCase):
    def test_verbal_confirmation_is_bound_to_ticket_and_speaker(self):
        resident = resident_fixture()
        request = LocalApproval("apaga el equipo", "Apagar el equipo", VERBAL, "power")
        reply = Future()
        resident.require_confirmation(request, PROFILE.id, reply)
        dialogue = Dialogue(enabled=False)
        result = dialogue.answer("apaga el equipo", reply.result())
        self.assertTrue(result.followup)
        confirmation = dialogue.turn("Sí, confirma la orden", 0).command
        self.assertIsInstance(confirmation, ApprovalAnswer)
        self.assertEqual(confirmation.ticket, resident.pending_approval.ticket)
        self.assertIsNone(dialogue.turn("sí", 0).command)
        with patch.object(resident, "run_voice_action") as run:
            bad = resident.request_voice(confirmation, "other")
            resident.deliver()
            self.assertTrue(bad.cancelled())
            old = confirmation
            replacement = Future()
            resident.require_confirmation(LocalApproval("reinicia el equipo", "Reiniciar", VERBAL, "power"),
                                          PROFILE.id, replacement)
            stale = resident.request_voice(old, PROFILE.id)
            resident.deliver()
            self.assertIn("No hay", stale.result())
            run.assert_not_called()
            current = ApprovalAnswer(resident.pending_approval.ticket, True)
            resident.request_voice(current, PROFILE.id)
            resident.deliver()
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], "reinicia el equipo")
            self.assertTrue(run.call_args.kwargs["approved"])
            self.assertIsNone(resident.pending_approval)
            resident.request_voice(current, PROFILE.id)
            resident.deliver()
            run.assert_called_once()

    def test_button_and_hotkey_only_approve_their_own_requests(self):
        resident = resident_fixture()
        reply = Future()
        resident.require_confirmation(LocalApproval("bloquea el equipo", "Bloquear", HOTKEY, "lock"), PROFILE.id, reply)
        old_callback = resident.tray.set_hotkey.call_args.args[0]
        resident.require_confirmation(LocalApproval("bloquea el equipo", "Bloquear", BUTTON, "lock"), PROFILE.id, Future())
        with patch.object(resident, "run_voice_action") as run, patch("resident.messagebox.askyesno", return_value=True):
            old_callback()
            run.assert_not_called()
            resident.confirm_voice()
            run.assert_called_once()
            old_callback()
            run.assert_called_once()

    def test_power_waits_and_can_be_cancelled_without_forcing_processes(self):
        resident = resident_fixture()
        with patch("resident.perform_power") as perform:
            notice = resident.schedule_power(PowerAction("restart"), PROFILE.id, resident.revision)
            self.assertIn("diez segundos", notice.message)
            delay, callback = resident.root.after.call_args.args
            self.assertEqual(delay, 10000)
            perform.assert_not_called()
            resident.cancel_pending()
            resident.root.after_cancel.assert_called_once()
            callback()
            perform.assert_not_called()
            resident.schedule_power(PowerAction("shutdown"), PROFILE.id, resident.revision)
            resident.root.after.call_args.args[1]()
            perform.assert_called_once_with("shutdown")

    def test_opt_out_is_explicit_and_revisions_revoke_queued_work(self):
        resident = resident_fixture()
        self.assertFalse(resident.can_use_voice(UNVERIFIED))
        resident.policy = SecurityPolicy("Libertad", False)
        self.assertTrue(resident.can_use_voice(UNVERIFIED))
        self.assertFalse(resident.can_use_voice(PROFILE.id))
        command = resident.request_voice("abre spotify", UNVERIFIED)
        resident.invalidate_voice()
        resident.deliver()
        self.assertTrue(command.cancelled())
        resident.assistant.submit_voice.assert_not_called()


class UpdateDiscoveryTest(TestCase):
    def test_four_component_releases_and_legacy_do_not_conflict(self):
        self.assertLess(version_tuple("0.6.4"), version_tuple("v0.6.4.1"))
        self.assertLess(version_tuple("0.6.4.1"), version_tuple("v0.6.5"))
        asset = dict(name="JARVIS.exe", digest="sha256:" + "a" * 64, size=15)
        data = [{"tag_name": "v0.6.5", "prerelease": True}, {"tag_name": "oops"},
                {"tag_name": "v0.6.4.2", "assets": [asset]}, {"tag_name": "v0.6.4.1", "assets": [asset]}]
        with patch("updater.urlopen", return_value=BytesIO(json.dumps(data).encode())):
            self.assertEqual(latest_update(), ("v0.6.4.2", "a" * 64, 15))
