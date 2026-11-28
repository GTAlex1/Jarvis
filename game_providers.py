"""Read local launcher metadata. Hand off through registered routes or existing shortcuts."""
import configparser
from dataclasses import replace
import json
import os
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import quote

from app_catalog import Application, Identity, collect_source, name_key
from windows_catalog import (LOCAL_FILE, exe_path, existing_exe, path_identity, registry_rows,
                             icon_executable, web_identity, desktop_entries)

URI_PROVIDERS = {
    "steam": r"steam://(?:rungameid|run)/[1-9]\d{0,19}/?",
    "epic": r"com\.epicgames\.launcher://apps/[\w.%:/~-]+\?action=launch(?:&silent=(?:true|false))?",
    "ubisoft": r"uplay://launch/[1-9]\d{0,15}(?:/\d+)?/?",
    "ea": r"(?:origin2?|ea)://(?:game/launch\?offerIds=|launchgame/|launch/)[\w.:%-]+",
    "battlenet": r"battlenet://[a-z0-9]{2,20}/?",
    "gog": r"goggalaxy://launch/[1-9]\d{0,19}/?",
}
LAUNCHERS = {
    "riotclientservices": "riot", "riotclientux": "riot",
    "hoyoplay": "hoyoplay", "hyp": "hoyoplay", "hoyoplaylauncher": "hoyoplay",
    "epicgameslauncher": "epic", "steam": "steam",
    "eadesktop": "ea", "ealauncher": "ea", "origin": "ea",
    "battle.net": "battlenet", "battle.net launcher": "battlenet",
    "ubisoftconnect": "ubisoft", "upc": "ubisoft", "uplay": "ubisoft",
    "galaxyclient": "gog", "galaxyclient service": "gog",
    "minecraftlauncher": "xbox", "minecraft": "xbox", "gamingapp": "xbox",
}
# These are names of observed game processes, never executable launch routes.
GAME_PROCESSES = {
    "valorant": ("VALORANT-Win64-Shipping.exe",),
    "league of legends": ("League of Legends.exe",),
    "teamfight tactics": ("League of Legends.exe",),
    "genshin impact": ("GenshinImpact.exe", "YuanShen.exe"),
    "honkai star rail": ("StarRail.exe",),
    "honkai impact 3rd": ("BH3.exe",),
    "zenless zone zero": ("ZenlessZoneZero.exe",),
    "rocket league": ("RocketLeague.exe",),
    "minecraft": ("Minecraft.Windows.exe",),
    "minecraft for windows": ("Minecraft.Windows.exe",),
}
GAME_STORES = {
    "valorant": "riot", "league of legends": "riot", "teamfight tactics": "riot",
    "genshin impact": "hoyoplay", "honkai star rail": "hoyoplay", "honkai impact 3rd": "hoyoplay",
    "zenless zone zero": "hoyoplay", "minecraft for windows": "xbox", "minecraft": "xbox",
    "minecraft java edition": "xbox", "rocket league": "epic",
}
GAME_ALIASES = {
    "valorant": ("valo",), "league of legends": ("lol",),
    "genshin impact": ("genshin",), "honkai star rail": ("honkai", "star rail", "hsr"),
    "honkai impact 3rd": ("honkai", "honkai impact"), "zenless zone zero": ("zzz", "zenless"),
    "minecraft for windows": ("minecraft", "minecraft bedrock"),
    "minecraft java edition": ("minecraft", "minecraft java"),
}


def provider_uri(value):
    return next((provider for provider, pattern in URI_PROVIDERS.items()
                 if re.fullmatch(pattern, value, re.I | re.ASCII)), "")


def read_shortcut_url(path):
    try:
        if path.stat().st_size > 65536:
            return ""
        raw = path.read_bytes()
        codec = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(raw.decode(codec, errors="replace"))
        return parser.get("InternetShortcut", "URL", fallback="").strip()
    except (OSError, configparser.Error, ValueError):
        return ""


def read_text(path, limit=2_000_000):
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        return data.decode("utf-8-sig", errors="replace") if len(data) <= limit else ""
    except OSError:
        return ""


def json_metadata(path):
    try:
        data = json.loads(read_text(path))
        return data if isinstance(data, dict) else {}
    except (ValueError, RecursionError):
        return {}


def win_path(value):
    return str(PureWindowsPath(value)) if isinstance(value, str) and LOCAL_FILE.fullmatch(value) else ""


def game_app(name, source, route, root="", executable="", backing="", note=""):
    evidence = list(path_identity(executable))
    if root := win_path(root):
        evidence.append(Identity("game_root", root))
    evidence.extend(Identity("game_image", image) for image in GAME_PROCESSES.get(name_key(name), ()))
    return Application(name, source, route, tuple(evidence), GAME_ALIASES.get(name_key(name), ()),
                       True, note, str(backing))


def classify_shortcuts(rows):
    for item in rows:
        if not isinstance(item, dict):
            continue
        name, path = item.get("Name"), win_path(item.get("Path"))
        if not isinstance(name, str) or not name or not path:
            continue
        suffix = PureWindowsPath(path).suffix.casefold()
        if suffix == ".url":
            url = read_shortcut_url(Path(path))
            if provider := provider_uri(url):
                yield game_app(name, provider, Identity("uri", url), backing=path)
            continue
        if suffix != ".lnk" or not (target := existing_exe(item.get("Target"))):
            continue
        launcher = LAUNCHERS.get(PureWindowsPath(target).stem.casefold())
        args = item.get("Arguments")
        args = args if isinstance(args, str) else ""
        key = name_key(name)
        appid = item.get("Id")
        appid = appid if isinstance(appid, str) else ""
        web = web_identity(appid)
        if not web:
            match = re.search(r'(?:^|\s)--app-id[=\s]+"?([a-p]{32})(?=["\s]|$)', args, re.I)
            if match:
                web = (Identity("webapp", match[1].casefold()),)
        if web:
            evidence = (*((Identity("aumid", appid),) if appid else ()), *web)
            yield Application(name, "shortcut", Identity("shortcut", path), evidence)
            continue
        if launcher and (key in GAME_STORES or (args and re.search(
                r"(?:--launch-product=|--game(?:[= ]|biz)|--exec(?:[= ])|--launch-game|"
                r"/gameId=|/launchGame=|(?:^| )-launch(?:[= ]))", args, re.I))):
            note = "Si el cliente muestra la ficha, pulsa Jugar para iniciar el juego." if launcher in {
                "riot", "hoyoplay", "xbox"} else ""
            yield game_app(name, launcher, Identity("shortcut", path), note=note)
        elif not launcher or name_key(PureWindowsPath(target).stem) in key or key in {
            "riot client", "ea app", "ubisoft connect", "hoyoplay", "gog galaxy",
            "battle net", "steam", "epic games launcher", "minecraft launcher", "xbox"
        }:
            yield Application(name, "shortcut", Identity("shortcut", path), path_identity(target))


def vdf(content):
    tokens = iter(re.findall(r'"(?:[^"\\]|\\.)*"|[{}]|//[^\n]*', content))
    stack = [{}]
    key = None
    for token in tokens:
        if token.startswith("//"):
            continue
        if token == "{":
            if key is None or len(stack) >= 32:
                return {}
            obj = {}
            stack[-1][key] = obj
            stack.append(obj)
            key = None
        elif token == "}":
            if len(stack) < 2 or key is not None:
                return {}
            stack.pop()
        else:
            value = token[1:-1].replace('\\\\', '\\').replace('\\"', '"')
            if key is None:
                key = value
            else:
                stack[-1][key] = value
                key = None
    return stack[0] if len(stack) == 1 and key is None else {}


def steam_games(roots):
    libraries = set(map(Path, roots))
    for base in tuple(libraries):
        data = vdf(read_text(base / "steamapps/libraryfolders.vdf")).get("libraryfolders", {})
        if not isinstance(data, dict):
            continue
        for key, library in data.items():
            if not key.isdecimal():
                continue
            location = library.get("path") if isinstance(library, dict) else library
            if path := win_path(location):
                libraries.add(Path(path))
    for library in sorted(libraries):
        for manifest in (library / "steamapps").glob("appmanifest_*.acf"):
            row = vdf(read_text(manifest)).get("AppState")
            if not isinstance(row, dict):
                continue
            title, appid, folder = (row.get(key, "") for key in ("name", "appid", "installdir"))
            if not (title and isinstance(appid, str) and re.fullmatch(r"[1-9]\d{0,19}", appid)
                    and isinstance(folder, str) and folder not in {".", ".."}
                    and re.fullmatch(r'[^\\/:*?"<>|]+', folder)):
                continue
            if title in {"Steamworks Common Redistributables", "Steam Linux Runtime"}:
                continue
            root = library / "steamapps/common" / folder
            if root.is_dir():
                yield game_app(title, "steam", Identity("uri", "steam://rungameid/" + appid),
                               str(root), backing=manifest)


def epic_games(manifest_dir):
    for manifest in manifest_dir.glob("*.item"):
        row = json_metadata(manifest)
        if row.get("bIsIncompleteInstall") or row.get("bIsApplication") is False:
            continue
        name, appid, root = (row.get(key) for key in ("DisplayName", "AppName", "InstallLocation"))
        component = r"[\w.-]{1,170}"
        if not (isinstance(name, str) and name and isinstance(appid, str)
                and re.fullmatch(component, appid) and (root := win_path(root)) and Path(root).is_dir()):
            continue
        ids = [row.get("CatalogNamespace"), row.get("CatalogItemId"), appid]
        product = ":".join(ids) if all(isinstance(i, str) and re.fullmatch(component, i) for i in ids) else appid
        exe = str(PureWindowsPath(root) / str(row.get("LaunchExecutable") or ""))
        route = Identity("uri", "com.epicgames.launcher://apps/" + quote(product, safe="") + "?action=launch")
        yield game_app(name, "epic", route, root, exe, manifest)


def registry_games(source, rows):
    for key, row in rows:
        name = row.get("gameName") or row.get("DisplayName")
        root = win_path(row.get("path") or row.get("InstallDir") or row.get("InstallLocation"))
        if not name or not root or not Path(root).is_dir():
            continue
        if source == "gog":
            # Galaxy game shortcuts generated by the client take precedence.
            # GOG standalone installers may register a native entry point.
            path = existing_exe(icon_executable(row.get("exe")))
            if path and PureWindowsPath(root) in PureWindowsPath(path).parents:
                yield game_app(name, source, Identity("file", path), root, path)
                continue
        if source == "ubisoft" and re.fullmatch(r"[1-9]\d{0,15}", key):
            yield game_app(name, source, Identity("uri", "uplay://launch/" + key), root)
            continue
        # No official launch route was found. Keep discovery separate and fail closed.
        yield game_app(name, source, Identity("unavailable", root + "|" + name), root,
                       note="Crea un acceso directo al juego desde su cliente y actualiza el catálogo.")


def publisher_games(installed, source, publishers, exclude):
    rows = ((key, row) for key, row in installed if re.search(
        publishers, row.get("Publisher", ""), re.I) and not re.search(exclude, row.get("DisplayName", ""), re.I))
    return registry_games(source, rows)


def hoyoplay_games(shell, installed, shortcuts):
    clients = (*shortcuts, *desktop_entries(shell))
    launcher = next((app for app in clients if not app.game and (
        any(i.kind == "exe" and LAUNCHERS.get(PureWindowsPath(i.value).stem.casefold()) == "hoyoplay"
            for i in app.evidence)
        or (app.route.kind == "appsfolder" and name_key(app.name) == "hoyoplay")
    )), None)
    if launcher is None:
        for _, row in installed:
            if name_key(row.get("DisplayName", "")) != "hoyoplay":
                continue
            path = existing_exe(icon_executable(row.get("DisplayIcon")))
            if path and LAUNCHERS.get(PureWindowsPath(path).stem.casefold()) == "hoyoplay":
                launcher = Application("HoYoPlay", "registry", Identity("file", path), path_identity(path))
                break
    for game in publisher_games(installed, "hoyoplay", r"hoyoverse|mihoyo|cognosphere", r"^hoyoplay|launcher"):
        if launcher is None:
            yield game
            continue
        # HoYoPlay can locate several games from its own library. Its normal
        # Windows entry is supported even when no per-game shortcut was created.
        # Keep product-specific identity separate from the shared launch route.
        yield replace(game, route=Identity("provider_client", launcher.route.kind + "|" + launcher.route.value),
                      note=f"Selecciona «{game.name}» y pulsa Jugar en HoYoPlay.")


def xbox_games(snapshot):
    for row in snapshot.get("Packages", ()):
        appid, root = row.get("Id", ""), win_path(row.get("Location"))
        if not root or "!" not in appid:
            continue
        package = appid.split("!", 1)[0]
        config = Path(root) / "MicrosoftGame.config"
        if not config.is_file() and not re.search(r"(?:minecraftuwp|gamingservices\.game)", package, re.I):
            continue
        name = row.get("Name") or package
        for entry in (*snapshot.get("Shell", ()), *snapshot.get("Start", ())):
            if (entry.get("Id") or entry.get("AppID")) == appid:
                name = entry.get("Name") or name
                break
        exe = str(PureWindowsPath(root) / str(row.get("Exe") or ""))
        app = game_app(name, "xbox", Identity("appsfolder", appid), root, exe)
        yield replace(app, evidence=(Identity("aumid", appid), *app.evidence))


def riot_games(program_data, installed):
    # Riot metadata is used for identification only. Client-created shortcuts
    # carry the supported game selection, authenticator and anticheat flow.
    riot = program_data / "Riot Games"
    metadata = json_metadata(riot / "RiotClientInstalls.json")
    associated = metadata.get("associated_client", {})
    roots = associated.keys() if isinstance(associated, dict) else ()
    names = {"valorant": "VALORANT", "league of legends": "League of Legends"}
    for value in roots:
        root = win_path(value)
        if not root or not Path(root).is_dir():
            continue
        parts = {part.casefold() for part in PureWindowsPath(root).parts}
        for key, name in names.items():
            if key in parts:
                yield game_app(name, "riot", Identity("unavailable", root + "|" + name), root,
                               backing=riot / "RiotClientInstalls.json",
                               note="Crea un acceso directo del juego desde Riot Client y actualiza el catálogo.")
    yield from publisher_games(installed, "riot", r"riot games", r"^riot |vanguard")


def ubisoft_games():
    installs = dict(registry_rows(r"Software\Ubisoft\Launcher\Installs", ("InstallDir", "DisplayName", "gameName")))
    products = dict(registry_rows(r"Software\Ubisoft\Launcher\Games", ("DisplayName", "Name")))
    for game_id, values in installs.items():
        product = products.get(game_id, {})
        yield from registry_games("ubisoft", ((game_id, {
            **values, "DisplayName": values.get("DisplayName") or product.get("DisplayName") or product.get("Name"),
        }),))


def discover_steam():
    steam_roots = {Path(root) for name, row in registry_rows(r"Software\Valve", ("SteamPath", "InstallPath"))
                   if name.casefold() == "steam" and (root := win_path(row.get("SteamPath") or row.get("InstallPath")))}
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        if root := os.environ.get(var):
            steam_roots.add(Path(root) / "Steam")
    return steam_games(steam_roots)


def game_entries(shell, installed, shortcuts, failed=None):
    failed = set() if failed is None else failed
    program_data = Path(os.environ.get("PROGRAMDATA") or Path.home())
    metadata = (
        ("steam", discover_steam),
        ("epic", lambda: epic_games(program_data / "Epic/EpicGamesLauncher/Data/Manifests")),
        ("riot", lambda: riot_games(program_data, installed)),
        ("hoyoplay", lambda: hoyoplay_games(shell, installed, shortcuts)),
        ("xbox", lambda: xbox_games(shell)),
        ("ea", lambda: publisher_games(installed, "ea", r"electronic arts|^ea$", r"^ea (app|desktop|anticheat)|origin")),
        ("ubisoft", ubisoft_games),
        ("battlenet", lambda: publisher_games(installed, "battlenet", r"blizzard", r"battle.net|agent")),
        ("gog", lambda: registry_games("gog", registry_rows(
            r"Software\GOG.com\Games", ("gameName", "path", "exe")))),
    )
    games = [app for app in shortcuts if app.game]
    for provider, discover in metadata:
        games.extend(collect_source(provider, discover, failed))
    # Combine records of a product within the same store, preserving distinct
    # installations and storefronts. Prefer generated links over manual fallbacks.
    games.sort(key=lambda app: (app.route.kind in {"unavailable", "provider_client"},
                                app.source in {"steam", "epic"} and not app.route.value.startswith(
                                    ("steam://rungameid/", "com.epicgames.launcher://apps/")),
                                app.backing.casefold().endswith(".url")))
    merged = {}
    for app in games:
        key = app.source, name_key(app.name)
        options = merged.setdefault(key, [])
        match = next((i for i, preferred in enumerate(options)
                      if preferred.key == app.key or app.route.kind in {"unavailable", "provider_client"}
                      or bool(preferred.backing.casefold().endswith(".url")) != bool(app.backing.casefold().endswith(".url"))
                      and preferred.route.kind == app.route.kind == "uri"), None)
        if match is None:
            options.append(app)
        else:
            preferred = options[match]
            options[match] = replace(preferred, evidence=tuple(dict.fromkeys((*preferred.evidence, *app.evidence))))
    return tuple(app for options in merged.values() for app in options)
