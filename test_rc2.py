import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from app_catalog import Application, Catalog, Identity, consolidate
from app_launch import Running, matches_identity
from dialogue import Dialogue, SelectedCommand
from game_providers import classify_shortcuts, game_app
from jarvis import Desktop, canonical_windows_name, execute
from windows_catalog import desktop_entries, exe_path, windows_inventory


class InventoryRegression(unittest.TestCase):
    def test_end_to_end_inventory_filters_game_binaries_without_losing_other_sources(self):
        web = "Chrome._crx_" + "a" * 32
        snapshot = {"Start": [{"Name": "Poke Gacha Online", "AppID": web}], "Links": ()}
        game = game_app("Rocket League", "epic", Identity("uri", "com.epicgames.launcher://apps/123?action=launch"),
                        r"E:\Games\RocketLeague")
        def local(name, path):
            return Application(name, "registry", Identity("file", path), (Identity("exe", path),))
        with (patch("windows_catalog.inventory", return_value=snapshot),
              patch("windows_catalog.uninstall_entries", return_value=()),
              patch("game_providers.game_entries", return_value=(game,)),
              patch("windows_catalog.registered_apps", return_value=(
                  local("Editor", r"D:\Editor\Editor.exe"), local("Rocket binary", r"E:\Games\RocketLeague\RocketLeague.exe"))),
              patch("windows_catalog.portable_folders", return_value=()),
              patch("windows_catalog.portable_apps", side_effect=PermissionError),
              self.assertLogs("app_catalog", "ERROR")):
            result = windows_inventory()
        self.assertEqual({app.name for app in result.entries}, {"Editor", "Poke Gacha Online", "Rocket League"})
        self.assertEqual(result.failed, {"portable"})

    def test_provider_crash_preserves_other_sources_and_previously_valid_rows(self):
        app = Application("Launcher game", "epic", Identity("uri", "test"))
        with TemporaryDirectory() as temp:
            def broken():
                raise NameError("broken provider")
            catalog = Catalog(temp + "/catalog.json", (("epic", Mock(side_effect=[(app,), NameError()])),
                                                        ("registry", broken)), lambda _: True)
            try:
                with self.assertLogs("app_catalog", "ERROR"):
                    self.assertEqual(catalog.refresh().result(timeout=2), None)
                    catalog.refresh(force=True).result(timeout=2)
                self.assertEqual(catalog.entries, (app,))
            finally:
                catalog.close()

    def test_web_apps_do_not_share_the_browser_identity(self):
        appid = "Chrome._crx_" + "a" * 32
        executable = r"D:\Chrome\chrome.exe"
        (pwa,) = desktop_entries({"Start": [{"Name": "Juego web", "AppID": appid, "Target": executable}]})
        shortcut = {"Name": "Juego web", "Id": appid, "Path": r"C:\Desktop\game.lnk", "Target": executable,
                    "Arguments": "--app-id=" + "a" * 32}
        with patch("game_providers.existing_exe", side_effect=exe_path):
            (link,) = classify_shortcuts((shortcut,))
        self.assertEqual(consolidate((pwa, link))[0].route.kind, "appsfolder")
        self.assertFalse(matches_identity(pwa, Running(4, executable, "Chrome", 1)))
        self.assertFalse(matches_identity(pwa, Running(4, executable, appid + ".Other", 1)))
        self.assertTrue(matches_identity(pwa, Running(4, executable, appid, 1)))
        desktop = Desktop.__new__(Desktop)
        desktop.index = Mock()
        desktop.index.snapshot.return_value = (pwa,)
        desktop.window_owners = {1: Running(4, executable, appid, 1, 5),
                                 2: Running(4, executable, "Chrome", 2, 5)}
        desktop.windows = lambda: [(1, "Sesión · juego", "chrome"), (2, "Google Chrome", "chrome")]
        desktop.api = Mock()
        self.assertIn("Juego web", execute(desktop, "cierra juego web"))
        desktop.api.PostMessageW.assert_called_once_with(1, 0x10, 0, 0)
        self.assertEqual(desktop.select_window("chrome")[0], 2)

    def test_commercial_labels_and_natural_confirmation(self):
        self.assertEqual(canonical_windows_name("Nombre técnico (Vulkan, 64-bit)", ""), "Nombre técnico")
        self.assertEqual(canonical_windows_name("Iniciador de Epic Games", "EpicGamesLauncher"), "Epic Games")
        self.assertEqual(canonical_windows_name("Archivo", "Code.exe"), "Visual Studio Code")
        self.assertEqual(canonical_windows_name("Rocket League (64-bit, DX11, Cooked)", ""), "Rocket League")
        desktop = Desktop.__new__(Desktop)
        desktop.windows = lambda: [(3, "Epic Games", "EpicGamesLauncher")]
        desktop.api = Mock()
        command = "cierra epic geims"
        result = execute(desktop, command, conversational=True)
        talk = Dialogue()
        self.assertIn("¿Quieres cerrar esa ventana?", talk.answer(command, result).speech)
        choice = talk.turn("Sí, adelante", 2).command
        self.assertIsInstance(choice, SelectedCommand)
        desktop.api.PostMessageW.assert_not_called()
        self.assertIn("Epic Games", execute(desktop, command, True, choice.option.target))


class ContextualVoice(unittest.TestCase):
    def test_english_sample_is_transcribed_with_the_optional_model(self):
        import english_voice
        from pathlib import Path
        from commands import parse
        from voice_probe import fixture
        from voice_recognition import SpanishRecognizer

        if not english_voice.installed():
            self.skipTest("Modelo inglés opcional no instalado")
        recognizer = SpanishRecognizer(english_voice.load())
        audio = fixture(Path(__file__).parent / "tests/voice", "rc2-open-firefox-en")
        text = recognizer.feed(audio) or recognizer.finish()
        self.assertIsNotNone(text)
        self.assertEqual(parse(text.text), ("open", "firefox"))

    def test_contextual_targets_are_always_confirmed_and_never_promoted_by_hints(self):
        from app_catalog import resolve
        from voice_context import ContextTitle

        examples = {"rocket lic": "Rocket League", "fortuna": "Fortnite",
                    "sin impacto": "Genshin Impact", "epic ellos": "Epic Games",
                    "poque gacho": "Poke Gacha Online", "poker online": "Poke Gacha Online"}
        names = set(examples.values())
        for raw, target in examples.items():
            with self.subTest(raw=raw):
                matches, approximate = resolve(ContextTitle(raw), names, lambda name: (name,))
                self.assertTrue(approximate)
                self.assertIn(target, matches)
        a = ("Epic Games", "Epic Game Store")
        self.assertEqual(set(resolve(ContextTitle("epic geims"), a, lambda n: (n,))[0]), set(a))
        self.assertEqual(resolve(ContextTitle("frase sin relación", ("Epic Games",)), a, lambda n: (n,)), ((), False))
        self.assertEqual(resolve(ContextTitle("Epic Games", ("Epic Game Store",)), a, lambda n: (n,)),
                         (("Epic Games",), False))

    def test_alias_correction_is_explicit_and_does_not_create_actions(self):
        from commands import parse
        from voice_adaptation import Adaptation
        from preferences import voice_settings

        neutral = Adaptation()
        options = neutral.corrected("rock lic", "Rocket League")
        self.assertEqual(neutral.aliases, ())
        self.assertEqual(parse(options.apply("abre rock lic")), ("open", "rocket league"))
        self.assertEqual(parse(options.apply("no abras rock lic")), None)
        with patch("preferences.read_value", return_value='{"enabled": true, "device": "webcam", "language": "en"}'):
            settings = voice_settings()
            self.assertEqual((settings.device, settings.language), ("webcam", "en"))
        with patch("preferences.read_value", return_value='{"device": "webcam"}'):
            self.assertEqual(voice_settings().language, "es")


class LaunchAndTray(unittest.TestCase):
    def test_game_start_has_separate_launcher_process_window_and_timeout_phases(self):
        from app_launch import launch_progress
        game = game_app("Rocket League", "epic", Identity("uri", "product"),
                        r"D:\Games\RocketLeague", r"D:\Games\RocketLeague\RocketLeague.exe",
                        note="Pulsa Jugar en el cliente.")
        launch = Running(2, r"C:\Epic\EpicGamesLauncher.exe", window=2)
        running = Running(3, r"D:\Games\RocketLeague\RocketLeague.exe")
        window = Running(3, running.executable, window=301)
        for records, seconds, state in (((launch,), 12, "launcher"), ((launch, running), 23, "starting"),
                                        ((launch, window), 31, "verified"), ((launch,), 46, "manual")):
            self.assertEqual(launch_progress(game, set(), records, 45, seconds).state, state)
        self.assertEqual(launch_progress(game, {window}, [window], 45, 0).state, "already_running")

    def test_submitting_game_releases_caller_before_verification(self):
        from threading import Event
        from app_launch import LaunchMonitor
        checked = Event()
        game = game_app("Stellar Race", "steam", Identity("uri", "steam://rungameid/1"),
                        r"D:\Steam\Stellar Race")
        monitor = LaunchMonitor(Mock(side_effect=[(), (Running(3, r"D:\Steam\Stellar Race\Run.exe", window=11),)]),
                                Mock(), lambda result: checked.set() if result.state == "verified" else None)
        try:
            self.assertIn("segundo plano", monitor.submit(game))
            self.assertTrue(checked.wait(3))
        finally:
            monitor.close()

    def test_window_snapshot_does_not_replace_command_window_ownership(self):
        desktop = Desktop.__new__(Desktop)
        desktop.api = Mock()
        desktop.api.EnumWindows.return_value = True
        desktop.window_callback = lambda callback: callback
        desktop.instances = Mock()
        desktop.instances.all.return_value = ()
        desktop.window_owners = {7: Running(1, "Editor.exe", window=7)}
        self.assertEqual(desktop.snapshot_windows(), ([], {}))
        self.assertEqual(desktop.running(), ())
        self.assertEqual(tuple(desktop.window_owners), (7,))
        self.assertEqual(desktop.windows(), [])
        self.assertEqual(desktop.window_owners, {})

    def test_icons_and_tray_version_handover_policy(self):
        from struct import unpack_from
        from tray_theme import ICONS, appearance
        from windows_tray import ActiveInstance, handover_kind
        from updater import VERSION
        self.assertEqual(VERSION, "0.6.5-rc.2")
        variants = [appearance(state)[0] for state in
                    ("waiting", "listening", "processing", "executing", "unavailable", "muted")]
        self.assertEqual(len(set(variants)), 6)
        for name in variants:
            data = (ICONS / f"{name}.ico").read_bytes()
            self.assertEqual(unpack_from("<HHH", data), (0, 1, 7))
            self.assertEqual({data[i] or 256 for i in range(6, 6 + 7*16, 16)}, {16, 24, 32, 48, 64, 128, 256})
        self.assertEqual(handover_kind(ActiveInstance(1, 21, VERSION, True), VERSION), "existing")
        self.assertEqual(handover_kind(ActiveInstance(1, 21, "0.6.4.2", False), VERSION), "manual")
        self.assertEqual(handover_kind(ActiveInstance(1, 21, "0.6.5-rc.1", True), VERSION), "cooperative")
        self.assertEqual(handover_kind(ActiveInstance(1, 21), VERSION), "manual")

    def test_menu_exposes_exit_and_state_controls(self):
        from resident import Resident
        from preferences import VoiceSettings

        app = Resident.__new__(Resident)
        for name in ("show", "toggle_microphone", "toggle_startup", "toggle_voice", "open_voice_settings",
                     "use_spanish", "use_english", "open_speakers", "open_adaptation", "open_security",
                     "configure_application_folders", "clear_application_folders", "confirm_voice", "cancel_voice",
                     "update_clicked", "restart", "quit"):
            setattr(app, name, Mock())
        app.microphone = app.autostart = True
        app.last_correction = app.available_update = None
        app.voice_options = VoiceSettings(language="en")
        labels = {label: (checked, action) for label, checked, action in
                  (item for item in app.menu_items() if item)}
        self.assertTrue(labels["Voz en inglés…"][0])
        self.assertIs(labels["Reiniciar JARVIS"][1], app.restart)
        self.assertIs(labels["Salir completamente"][1], app.quit)
        self.assertIn("Buscar actualizaciones", labels)



@unittest.skipUnless(sys.platform == "win32", "Requiere Windows")
class NativeWindowIdentity(unittest.TestCase):
    def test_can_read_the_explicit_appid_in_a_real_window_property_store(self):
        import ctypes as c
        from ctypes import wintypes as w
        import tkinter as tk
        from windows_appid import APP_ID, IID_PROPERTY_STORE, PropertyKey, PropertyValue

        root = tk.Tk()
        root.title("JARVIS native AppID fixture")
        root.update()
        desktop = Desktop()
        api = desktop.instances.window_aumid
        hwnd = next(handle for handle, caption, _ in desktop.windows() if caption == root.title())
        value = PropertyValue()
        appid = ("Chromium._crx_" + "c" * 32)
        text = c.create_unicode_buffer(appid)
        value.type = 31
        value.payload[0] = c.cast(text, c.c_void_p).value
        status = api.init(None, 2)
        store = c.c_void_p()
        try:
            self.assertGreaterEqual(api.open(hwnd, c.byref(IID_PROPERTY_STORE), c.byref(store)), 0)
            methods = c.cast(store, c.POINTER(c.POINTER(c.c_void_p))).contents
            set_value = c.WINFUNCTYPE(w.LONG, c.c_void_p, c.POINTER(PropertyKey),
                                     c.POINTER(PropertyValue))(methods[6])
            self.assertGreaterEqual(set_value(store, c.byref(APP_ID), c.byref(value)), 0)
            self.assertEqual(api(hwnd), appid)
            self.assertTrue(any(owner.aumid == appid for owner in desktop.running()))
            self.assertGreaterEqual(set_value(store, c.byref(APP_ID), c.byref(PropertyValue())), 0)
        finally:
            if store:
                methods = c.cast(store, c.POINTER(c.POINTER(c.c_void_p))).contents
                api.release(methods[2])(store)
            if status >= 0:
                api.uninit()
            desktop.close()
            root.destroy()
