"""Discover Windows applications without using input as a shell command."""
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess

from app_catalog import Application, Catalog, Discovery, Identity, collect_source, name_key

CURRENT_VERSION = r"Software\Microsoft\Windows\CurrentVersion"
BLOCKED_EXECUTABLE = re.compile(
    r"^(?:cmd|powershell|pwsh|wscript|cscript|mshta|rundll32|regsvr32|msiexec|"
    r"(?:un)?install\w*|unins\d*|setup\w*|crash(?:report|handler)\w*)\.exe$", re.I)
LOCAL_FILE = re.compile(r"^[a-z]:[\\/][^\x00-\x1f:*?\"<>|]+$", re.I)
SHELL_ID = re.compile(r"^[\w{}. !#+@(),/\\:%&'-]{1,1024}$")
KNOWN_APP_ALIASES = {
    "visual studio code": ("vscode", "vs code", "visual", "code"),
    "google chrome": ("chrome", "navegador", "browser"),
    "microsoft edge": ("edge", "navegador", "browser"),
    "mozilla firefox": ("firefox", "navegador", "browser"),
    "firefox": ("navegador", "browser"),
    "brave": ("navegador", "browser"),
    "brave browser": ("brave", "navegador", "browser"),
    "opera": ("navegador", "browser"),
    "vivaldi": ("navegador", "browser"),
    "calculator": ("calculadora", "calc"),
    "calculadora": ("calculator", "calc"),
    "notepad": ("bloc de notas",),
    "bloc de notas": ("notepad",),
}

# One bounded query per refresh. The script contains no values from voice/text.
INVENTORY = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$shell = New-Object -ComObject Shell.Application
$wsh = New-Object -ComObject WScript.Shell
$roots = @('StartMenu','CommonStartMenu','DesktopDirectory','CommonDesktopDirectory') |
    ForEach-Object { [Environment]::GetFolderPath($_) } | Where-Object { $_ } | Select-Object -Unique
$links = @(foreach ($root in $roots) {
    foreach ($entry in (Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.lnk','.url' } | Select-Object -First 3000)) {
        if ($entry.Extension -eq '.lnk') {
            try { $link = $wsh.CreateShortcut($entry.FullName) } catch { continue }
            $id = $shell.NameSpace($entry.DirectoryName).ParseName($entry.Name).ExtendedProperty('System.AppUserModel.ID')
            @{ Name=$entry.BaseName; Path=$entry.FullName; Target=$link.TargetPath; Arguments=$link.Arguments; Id=$id }
        } else { @{ Name=$entry.BaseName; Path=$entry.FullName } }
    }
})
$folder = $shell.NameSpace('shell:AppsFolder')
$items = @(foreach ($item in $folder.Items()) {
    @{ Name=$item.Name; Id=$item.ExtendedProperty('System.AppUserModel.ID')
       Target=$item.ExtendedProperty('System.Link.TargetParsingPath') }
})
$apps = @(Get-StartApps | Select-Object Name, AppID)
$packages = @(foreach ($pkg in (Get-AppxPackage -PackageTypeFilter Main)) {
    try {
        $manifest = Get-AppxPackageManifest $pkg -ErrorAction Stop
        foreach ($app in $manifest.Package.Applications.Application) {
            if (!$app.Id -or $app.VisualElements.AppListEntry -eq 'none') { continue }
            $name = [string]$app.VisualElements.DisplayName
            if (!$name -or $name.StartsWith('ms-resource:')) { $name = $pkg.Name }
            @{ Name=$name; Id=($pkg.PackageFamilyName + '!' + $app.Id)
               Location=$pkg.InstallLocation; Exe=$app.Executable }
        }
    } catch {}
})
ConvertTo-Json -InputObject @{ Links=$links; Shell=$items; Start=$apps; Packages=$packages } -Depth 5 -Compress
"""


def registry_rows(path, values):
    import winreg

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            access = winreg.KEY_READ | view
            try:
                with winreg.OpenKey(hive, path, 0, access) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for index in range(count):
                        try:
                            name = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, name, 0, access) as key:
                                row = {}
                                for value in values:
                                    try:
                                        data, _ = winreg.QueryValueEx(key, value)
                                    except OSError:
                                        continue
                                    if isinstance(data, str):
                                        row[value] = os.path.expandvars(data)
                                yield name, row
                        except OSError:
                            continue
            except OSError:
                continue


def inventory():
    system = Path(os.environ["SystemRoot"]) / "System32"
    powershell = system / "WindowsPowerShell/v1.0/powershell.exe"
    try:
        result = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", INVENTORY],
                                capture_output=True, encoding="utf-8-sig", check=True,
                                timeout=35, creationflags=subprocess.CREATE_NO_WINDOW)
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError("El inventario no es un objeto.")
        return data
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        raise OSError("No se pudo leer el catálogo de Windows.") from error


def exe_path(value):
    value = os.path.expandvars(str(value or "").strip().strip('"'))
    path = PureWindowsPath(value)
    if (LOCAL_FILE.fullmatch(value) and ".." not in path.parts and path.suffix.casefold() == ".exe"
            and not BLOCKED_EXECUTABLE.match(path.name)):
        return str(path)
    return ""


def existing_exe(value):
    path = exe_path(value)
    try:
        return path if path and Path(path).is_file() else ""
    except OSError:
        return ""


def path_identity(value):
    path = exe_path(value)
    return (Identity("exe", path),) if path else ()


def web_identity(value):
    match = re.search(r"(?i)(?:^|[._=])(?:crx_)?([a-p]{32})(?=$|[. _\"])", value or "")
    return (Identity("webapp", match[1].casefold()),) if match else ()


def desktop_entries(snapshot):
    seen = set()
    for group in ("Shell", "Start", "Packages"):
        for item in snapshot.get(group, ()):
            if not isinstance(item, dict):
                continue
            appid = item.get("Id") or item.get("AppID")
            name = item.get("Name")
            if not (isinstance(appid, str) and isinstance(name, str) and name
                    and SHELL_ID.fullmatch(appid) and appid.casefold() not in seen):
                continue
            seen.add(appid.casefold())
            web = web_identity(appid)
            evidence = (Identity("aumid", appid), *web)
            target = item.get("Target") or appid
            if group == "Packages" and item.get("Location") and item.get("Exe"):
                target = str(PureWindowsPath(item["Location"]) / item["Exe"])
            yield Application(name, "start", Identity("appsfolder", appid),
                              (*evidence, *(path_identity(target) if not web else ())), KNOWN_APP_ALIASES.get(name_key(name), ()))


UNINSTALL_FIELDS = ("DisplayName", "DisplayIcon", "InstallLocation", "Publisher")
def uninstall_entries():
    return registry_rows(CURRENT_VERSION + r"\Uninstall", UNINSTALL_FIELDS)


def icon_executable(value):
    # A DisplayIcon can be an EXE with a resource index. Never use UninstallString.
    return re.sub(r",\s*-?\d+\s*$", "", value or "").strip().strip('"')


def registered_apps(uninstall):
    for _, row in registry_rows(CURRENT_VERSION + r"\App Paths", ("",)):
        if path := existing_exe(row.get("")):
            name = PureWindowsPath(path).stem
            yield Application(name, "registry", Identity("file", path), path_identity(path))
    for _, row in uninstall:
        name = row.get("DisplayName")
        if name and (path := existing_exe(icon_executable(row.get("DisplayIcon")))):
            yield Application(name, "registry", Identity("file", path), path_identity(path),
                              KNOWN_APP_ALIASES.get(name_key(name), ()))


def portable_folders():
    from preferences import application_folders

    folders = application_folders()
    home = Path.home()
    return tuple(dict.fromkeys((str(home / "PortableApps"), str(home / "Games"), *(
        folder for folder in folders[:24] if isinstance(folder, str) and LOCAL_FILE.fullmatch(folder)
    ))))


def portable_apps(folders):
    remaining = 1200
    for folder in folders:
        base = Path(folder)
        if not base.is_dir() or base == Path(base.anchor) or base.is_symlink() or base.is_junction():
            continue
        for root, dirs, files in os.walk(base, followlinks=False):
            parent = Path(root)
            dirs[:] = [name for name in dirs if len(parent.relative_to(base).parts) < 2
                       and not (parent / name).is_symlink() and not (parent / name).is_junction()
                       and name.casefold() not in {"redist", "_commonredist", "plugins", "data"}]
            remaining -= len(files) + 1
            for filename in files[:max(0, remaining + len(files))]:
                if path := existing_exe(parent / filename):
                    yield Application(Path(path).stem, "portable", Identity("file", path), path_identity(path))
            if remaining <= 0:
                return


def local_exists(path, directory=False):
    try:
        item = Path(path)
        return item.is_dir() if directory else item.is_file()
    except OSError:
        return False


def provider_client(app):
    from dataclasses import replace
    from game_providers import LAUNCHERS

    kind, _, value = app.route.value.partition("|")
    if app.source != "hoyoplay" or kind not in {"file", "appsfolder", "shortcut"}:
        return None
    if kind == "file" and LAUNCHERS.get(PureWindowsPath(value).stem.casefold()) != app.source:
        return None
    return replace(app, route=Identity(kind, value), evidence=(), backing="")


def valid_route(app):
    from game_providers import provider_uri

    route = app.route
    if route.kind == "provider_client":
        client = provider_client(app)
        return client is not None and valid_route(client)
    if app.backing and not local_exists(app.backing):
        return False
    roots = tuple(identity.value for identity in app.evidence if identity.kind == "game_root")
    if roots and route.kind in {"uri", "unavailable"} and not any(local_exists(root, directory=True) for root in roots):
        return False
    if route.kind == "unavailable":
        return bool(roots)
    if route.kind == "file":
        return bool(existing_exe(route.value))
    if route.kind == "shortcut":
        return (bool(LOCAL_FILE.fullmatch(route.value))
                and PureWindowsPath(route.value).suffix.casefold() == ".lnk"
                and local_exists(route.value))
    if route.kind == "appsfolder":
        if not SHELL_ID.fullmatch(route.value) or route.value.casefold().startswith(("shell:", "::")):
            return False
        return bool(existing_exe(route.value)) if exe_path(route.value) else True
    if route.kind == "uri":
        return provider_uri(route.value) == app.source
    return False


def start_application(app):
    if not valid_route(app):
        raise OSError("La ruta de la aplicación ya no está disponible o no es compatible.")
    from game_providers import read_shortcut_url

    route = app.route
    if route.kind == "provider_client":
        return start_application(provider_client(app))
    if route.kind == "uri" and app.backing and app.backing.casefold().endswith(".url"):
        if read_shortcut_url(Path(app.backing)) != route.value:
            raise OSError("El acceso directo cambió. Actualiza el catálogo y vuelve a intentarlo.")
    target = "shell:AppsFolder\\" + route.value if route.kind == "appsfolder" else route.value
    if route.kind == "file":
        os.startfile(target, cwd=str(Path(target).parent))
    else:
        os.startfile(target)


def catalog():
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "JARVIS"
    return Catalog(local / "applications-v1.json", (("windows", windows_inventory),), valid_route)


def windows_inventory():
    from game_providers import GAME_STORES, LAUNCHERS, classify_shortcuts, game_app, game_entries

    failed = set()
    (shell,) = collect_source("Windows", lambda: (inventory(),), failed, ("start", "shortcut")) or ({},)
    installed = collect_source("registry", uninstall_entries, failed)
    shortcuts = collect_source("shortcut", lambda: classify_shortcuts(shell.get("Links") or ()), failed)
    games = game_entries(shell, installed, shortcuts, failed)
    game_names = {name_key(app.name) for app in games}
    game_roots = {PureWindowsPath(identity.value) for app in games for identity in app.evidence
                  if identity.kind == "game_root" and identity.value}
    entries = list(games)
    conventional = (
        collect_source("start", lambda: desktop_entries(shell), failed),
        shortcuts,
        collect_source("registry", lambda: registered_apps(installed), failed),
        collect_source("portable", lambda: portable_apps(portable_folders()), failed),
    )
    for app in (app for feed in conventional for app in feed):
        key = name_key(app.name)
        if app.game or key in game_names:
            continue
        if key in GAME_STORES and app.source == "start":
            entries.append(game_app(app.name, GAME_STORES[key], app.route,
                                    note="Si aparece el cliente, selecciona Jugar en el juego solicitado."))
            game_names.add(key)
            continue
        if key in GAME_STORES and any(
            PureWindowsPath(identity.value).stem.casefold() in LAUNCHERS
            for identity in app.evidence if identity.kind == "exe"
        ):
            continue
        if app.source in {"portable", "registry"} and any(
            game_roots.intersection(PureWindowsPath(identity.value).parents)
            for identity in app.evidence if identity.kind == "exe"
        ):
            continue
        entries.append(app)
    return Discovery(tuple(entries), frozenset(failed))
