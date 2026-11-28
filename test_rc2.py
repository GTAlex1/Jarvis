from pathlib import PureWindowsPath
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
