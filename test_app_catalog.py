import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock, patch

from app_catalog import Application, Catalog, Identity, consolidate, labels, resolve
from app_launch import Running, launch_verified, matches_identity
from commands import parse
from dialogue import Clarification
from game_providers import classify_shortcuts, epic_games, game_app, provider_uri, steam_games, vdf
from jarvis import Desktop, execute
from permissions import SecurityPolicy
from voice_authorization import LocalApproval
from windows_catalog import desktop_entries, exe_path, valid_route
from updater import version_tuple


def application(name, path, source="registry", aliases=()):
    return Application(name, source, Identity("file", path), (Identity("exe", path),), aliases)


class CatalogTest(unittest.TestCase):
    def test_exact_identity_and_fuzzy_distinguish_variants(self):
        spotify = application("Spotify", r"D:\Music\Spotify.exe")
        vscode = application("Visual Studio Code", r"E:\Editors\Code.exe", aliases=("visual",))
        insider = application("Visual Studio Code Insiders", r"E:\Editors\Insiders.exe")
        apps = spotify, vscode, insider
        self.assertEqual(resolve("VISUAL", apps, labels), ((vscode,), False))
        self.assertEqual(resolve("code", apps, labels), ((vscode,), False))
        self.assertEqual(resolve("Spotfy", apps, labels), ((spotify,), True))
        self.assertEqual(resolve("Visual Studio", apps, labels), ((vscode, insider), True))
        self.assertEqual(resolve("VSC", apps, labels)[0][0], vscode)
        self.assertEqual(resolve("inexistente", apps, labels), ((), False))

    def test_same_binary_deduplicates_sources_but_preserves_different_copies(self):
        path = r"D:\Pack\Writer.exe"
        left = application("Writer", path, "portable")
        right = application("Writer", r"E:\Pack\Writer.exe", "registry")
        start = Application("Writer Local", "start", Identity("appsfolder", "Writer.Id"),
                            (Identity("exe", path),))
        apps = consolidate((left, right, start))
        self.assertEqual(len(apps), 2)
        self.assertEqual(set(resolve("writer", apps, labels)[0]), set(apps))

    def test_shared_binary_does_not_merge_distinct_packaged_ids(self):
        path = r"E:\Browser\Browser.exe"
        first = Application("Main", "start", Identity("appsfolder", "Shared!Main"), (Identity("exe", path),))
        second = Application("Alt", "start", Identity("appsfolder", "Shared!Alt"), (Identity("exe", path),))
        self.assertEqual(len(consolidate((first, second))), 2)

    def test_async_refresh_cache_and_uninstall(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "cache.json"
            data = [application("A", r"E:\A.exe")]
            blocked = Event()
            def discover():
                self.assertTrue(blocked.wait(3))
                return tuple(data)
            cat = Catalog(path, (("test", discover),), lambda _: True)
            try:
                self.assertEqual(cat.snapshot(), ())
                blocked.set()
                cat.refresh().result(timeout=3)
                self.assertEqual(cat.snapshot(), tuple(data))
                restored = Catalog(path, (("test", Mock(side_effect=AssertionError)),), lambda _: True)
                try:
                    self.assertEqual(restored.snapshot(), tuple(data))
                finally:
                    restored.close()
                data.clear()
                cat.refresh(force=True).result(timeout=3)
                self.assertEqual(cat.snapshot(), ())
                self.assertEqual(json.loads(path.read_text())["entries"], [])
            finally:
                cat.close()

    def test_cache_falls_back_on_access_denied_and_ignores_corruption(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "cache.json"
            path.write_text("broken")
            target = application("A", r"D:\A.exe", "windows")
            provider = Mock(side_effect=[(target,), PermissionError()])
            cat = Catalog(path, (("windows", provider),), lambda _: True)
            try:
                cat.refresh().result(timeout=3)
                cat.refresh(force=True).result(timeout=3)
                self.assertEqual(cat.snapshot(), (target,))
            finally:
                cat.close()

    def test_bare_speech_cannot_be_used_as_command_or_unc_path(self):
        for data in ("cmd.exe /c something", r"\\server\test.exe", r"D:\cmd.exe", r"D:\safe.exe:alternate",
                     r"D:\x\..\test.exe", r"Y:\some.bat", "C:/Temp/file.exe\n--foo"):
            self.assertEqual(exe_path(data), "", data)
        self.assertEqual(exe_path("D:/Installed/Program App.exe"), r"D:\Installed\Program App.exe")
        for data in ("https://example.com/game", "file:///a.exe", "steam://install/23", "steam://run/23//+foo",
                     "com.epicgames.launcher://apps/test?action=uninstall"):
            self.assertEqual(provider_uri(data), "", data)
        self.assertFalse(valid_route(Application("X", "epic", Identity("uri", "steam://run/12"))))

    def test_package_identity_and_legacy_start_entries(self):
        apps = tuple(desktop_entries({"Shell": [{"Name": "Fotos", "Id": "Microsoft.Photos_xyz!App"}],
                                     "Start": [{"Name": "Editor", "AppID": r"D:\Tools\Edit.exe"}],
                                     "Packages": [{"Name": "Juego", "Id": "Example.Game_xyz!Main",
                                                   "Location": r"E:\XboxGames\Game", "Exe": "Game.exe"}]}))
        self.assertEqual(len(apps), 3)
        self.assertIn(Identity("exe", r"D:\Tools\Edit.exe"), apps[1].evidence)
        self.assertTrue(matches_identity(apps[2], Running(20, "", "Example.Game_xyz!Main")))

    def test_shortcuts_and_play_providers(self):
        cases = [
            ("Valorant", "RiotClientServices", "", "riot"),
            ("Genshin Impact", "HoYoPlay", "", "hoyoplay"),
            ("Minecraft Java Edition", "MinecraftLauncher", "", "xbox"),
            ("EA Game", "EADesktop", "--launch-game foo", "ea"),
            ("Ubisoft Game", "UbisoftConnect", "-launch 123", "ubisoft"),
            ("Blizzard Game", "Battle.net Launcher", "--exec launch WTCG", "battlenet"),
            ("GOG Game", "GalaxyClient", "/gameId=66", "gog"),
        ]
        with patch("game_providers.existing_exe", side_effect=exe_path):
            for name, binary, args, source in cases:
                with self.subTest(name=name):
                    row = {"Name": name, "Path": r"D:\Desktop\Game.lnk",
                           "Target": "E:/Programs/" + binary + ".exe", "Arguments": args}
                    (app,) = tuple(classify_shortcuts((row,)))
                    self.assertEqual(app.source, source)
                    self.assertTrue(app.game)
                    self.assertFalse(matches_identity(app, Running(1, row["Target"], window=1)))

    def test_steam_manifest_and_legacy_vdf_syntax(self):
        self.assertEqual(vdf(r'"libraryfolders" { "1" "D:\\SteamLibrary" }'),
                         {"libraryfolders": {"1": r"D:\SteamLibrary"}})
        self.assertEqual(vdf('"a" { "b" '), {})
        with TemporaryDirectory() as folder:
            steam_apps = Path(folder) / "steamapps"
            (steam_apps / "common/Space Adventure").mkdir(parents=True)
            manifest = steam_apps / "appmanifest_123.acf"
            manifest.write_text('"AppState" { "appid" "123" "name" "Space Adventure" "installdir" "Space Adventure" }')
            (game,) = tuple(steam_games((folder,)))
            self.assertEqual(game.route.value, "steam://rungameid/123")
            manifest.write_text('"AppState" { "appid" "123" "name" "Space Adventure" "installdir" ".." }')
            self.assertEqual(tuple(steam_games((folder,))), ())

    def test_epic_builds_product_route_without_running_manifest_args(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "RocketLeague").mkdir()
            manifest = root / "game.item"
            manifest.write_text(json.dumps({"DisplayName": "Rocket League", "AppName": "Sugar",
                                            "CatalogNamespace": "namespace", "CatalogItemId": "item",
                                            "InstallLocation": str(root / "RocketLeague"),
                                            "LaunchExecutable": "RocketLeague.exe", "LaunchCommand": "ignored"}))
            with patch("game_providers.win_path", side_effect=lambda value: value or ""):
                (game,) = tuple(epic_games(root))
            self.assertEqual(game.route.value, "com.epicgames.launcher://apps/namespace%3Aitem%3ASugar?action=launch")
            self.assertEqual(game.aliases, ())

    def test_independent_app_on_other_drive_forwards_only_catalog_route(self):
        app = application("Editor portable", r"F:\Portables\Edit.exe", "portable")
        desktop = Desktop.__new__(Desktop)
        desktop.applications = lambda: (app,)
        desktop.running = Mock(side_effect=[(), (Running(2, r"F:\Portables\Edit.exe", window=3),)])
        with patch("jarvis.start_application") as launcher:
            self.assertIn("Comprobé", execute(desktop, "open the editor portable"))
            launcher.assert_called_once_with(app)

    def test_ambiguous_browser_and_sensitive_target(self):
        desktop = Desktop.__new__(Desktop)
        desktop.applications = lambda: (
            application("Chrome", r"D:\Chrome.exe", aliases=("navegador",)),
            application("Edge", r"E:\Edge.exe", aliases=("navegador",)),
            application("Nombre", r"E:\control.exe", aliases=("panel local",)),
        )
        with patch("jarvis.start_application") as launcher:
            options = execute(desktop, "abre el navegador", conversational=True)
            self.assertIsInstance(options, Clarification)
            self.assertEqual(len(options.options), 2)
            restricted = execute(desktop, "abre panel local", conversational=True,
                                 policy=SecurityPolicy("Equilibrado"))
            self.assertIsInstance(restricted, LocalApproval)
            launcher.assert_not_called()

    def test_alias_of_a_running_game_and_multiple_instances(self):
        game = game_app("Honkai: Star Rail", "hoyoplay", Identity("shortcut", r"E:\StarRail.lnk"))
        desktop = Desktop.__new__(Desktop)
        desktop.index = Mock()
        desktop.index.snapshot.return_value = (game,)
        desktop.screens = lambda: {2: ((0, 0, 1920, 1080), False)}
        desktop.windows = lambda: [(1, "Some localized title", "StarRail"),
                                   (2, "Another title", "StarRail")]
        desktop.window_owners = {1: Running(42, r"E:\Game\StarRail.exe", window=1, started=23),
                                 2: Running(73, r"E:\Game\StarRail.exe", window=2, started=52)}
        result = execute(desktop, "pon el honkai en la segunda pantalla", conversational=True)
        self.assertIsInstance(result, Clarification)
        self.assertEqual(len(result.options), 2)
        selection = result.options[0].target
        desktop.window_owners[1] = Running(42, r"E:\Game\StarRail.exe", window=1, started=99)
        with self.assertRaisesRegex(ValueError, "ha cambiado"):
            desktop.select_window("honkai", selection)

    def test_english_spanish_parser_and_updater(self):
        self.assertEqual(parse("put VSCode on the left"), ("place", "vscode", "left", None))
        self.assertEqual(parse("pon el honkai en la segunda pantalla"), ("place", "honkai", "monitor", 2))
        self.assertEqual(parse("Pon el Minecraft a pantalla completa"), ("place", "minecraft", "full", None))
        self.assertEqual(parse("actualiza aplicaciones"), ("refresh_apps",))
        self.assertIsNone(parse("do not open Spotify"))
        self.assertEqual(parse("Could you open the calculator, please?"), ("open", "calculator"))
        self.assertLess(version_tuple("0.6.4.2"), version_tuple("0.6.5-rc.1"))
        self.assertLess(version_tuple("0.6.5-rc.1"), version_tuple("0.6.5"))


class LaunchTest(unittest.TestCase):
    def setUp(self):
        self.game = game_app("VALORANT", "riot", Identity("shortcut", r"E:\Valorant.lnk"),
                             root=r"E:\Riot Games\VALORANT")
        self.launcher = Running(10, r"E:\Riot Games\RiotClientServices.exe", window=2)
        self.engine = Running(20, r"E:\Riot Games\VALORANT\Live\VALORANT-Win64-Shipping.exe", window=3)
        self.other = Running(30, r"D:\Other\VALORANT-Win64-Shipping.exe", window=4)

    def test_just_launcher_is_not_success(self):
        start = Mock()
        result = launch_verified(self.game, Mock(side_effect=[(), (self.launcher,)]), start, timeout=0)
        self.assertEqual(result.state, "unverified")
        start.assert_called_once_with(self.game)
        self.assertFalse(matches_identity(self.game, self.other))

    def test_new_game_process_and_already_open_game_are_distinct(self):
        result = launch_verified(self.game, Mock(side_effect=[(), (self.launcher, self.engine)]), Mock(), timeout=0)
        self.assertEqual(result.state, "verified")
        result = launch_verified(self.game, lambda: (self.engine,), Mock(), timeout=0)
        self.assertEqual(result.state, "already_running")

    def test_permission_error_is_not_reported_as_success(self):
        start = Mock(side_effect=PermissionError("No autorizado"))
        with self.assertRaises(PermissionError):
            launch_verified(self.game, lambda: (), start, timeout=0)

    def test_missing_route_is_never_invoked(self):
        start = Mock()
        app = game_app("Un juego", "battlenet", Identity("unavailable", "x"))
        self.assertEqual(launch_verified(app, Mock(), start, timeout=0).state, "unavailable")
        start.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Requiere Windows")
class NativeInventoryTest(unittest.TestCase):
    def test_windows_inventory_and_current_process(self):
        from windows_catalog import inventory
        desktop = Desktop()
        try:
            native = inventory()
            self.assertEqual(set(native), {"Links", "Shell", "Start", "Packages"})
            self.assertTrue(tuple(desktop_entries(native)))
            self.assertIn(Path(sys.executable).name.casefold(),
                          {Path(process.executable).name.casefold() for process in desktop.running()})
        finally:
            desktop.close()
