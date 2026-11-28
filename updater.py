"""Download a verified Windows executable from this project's GitHub Releases."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

VERSION = "0.6.5-rc.2"
REPO = "GTAlex1/Jarvis"
ASSET = "JARVIS.exe"
MAX_SIZE = 100 * 1024 * 1024

# The helper runs after the packaged app closes. Windows may retain a lock
# briefly while the PyInstaller parent process cleans up.
INSTALL = r"""
$ErrorActionPreference = 'Stop'
$target = $env:JARVIS_UPDATE_TARGET
$staged = $env:JARVIS_UPDATE_STAGED
$backup = $staged + '.backup'
$receipt = $staged + '.ready'
$logDir = Join-Path $env:LOCALAPPDATA 'JARVIS'
$log = Join-Path $logDir 'actualizacion.log'
$nl = [Environment]::NewLine
$replaced = $false
$newApp = $null
$step = 'Preparar la actualización'
try {
    [IO.Directory]::CreateDirectory($logDir) | Out-Null
    $step = 'Esperar al cierre de JARVIS'
    $deadline = (Get-Date).AddSeconds(60)
    while (Get-Process -Id ([int]$env:JARVIS_UPDATE_PID) -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw 'JARVIS sigue abierto después de 60 segundos.' }
        Start-Sleep -Milliseconds 200
    }
    $step = 'Sustituir el ejecutable'
    # PyInstaller's parent can retain the executable after its Python child exits.
    $deadline = (Get-Date).AddSeconds(60)
    while (-not $replaced) {
        try {
            [IO.File]::Replace($staged, $target, $backup)
            $replaced = $true
        } catch {
            if ((Get-Date) -gt $deadline) { throw }
            Start-Sleep -Milliseconds 300
        }
    }
    $step = 'Abrir la nueva versión'
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    $env:JARVIS_UPDATE_RECEIPT = $receipt
    $newApp = Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target) -PassThru -ErrorAction Stop
    $step = 'Comprobar que aparece la interfaz'
    $seconds = 40
    if ($env:JARVIS_UPDATE_TEST -eq '1' -and $env:JARVIS_TEST_RECEIPT_TIMEOUT) {
        $seconds = [int]$env:JARVIS_TEST_RECEIPT_TIMEOUT
    }
    $deadline = (Get-Date).AddSeconds($seconds)
    while (-not (Test-Path -LiteralPath $receipt)) {
        if ($newApp.HasExited) { throw "El ejecutable se cerró con código $($newApp.ExitCode)." }
        if ((Get-Date) -gt $deadline) { throw 'La nueva versión sigue ejecutándose, pero no confirmó que la interfaz estuviera lista.' }
        Start-Sleep -Milliseconds 200
    }
    $version = [IO.File]::ReadAllText($receipt)
    if ($env:JARVIS_UPDATE_EXPECTED -and $version -ne $env:JARVIS_UPDATE_EXPECTED) {
        throw 'El ejecutable abierto no confirmó la versión descargada.'
    }
    [IO.File]::WriteAllText($log, "Actualización correcta a $version$nl$target")
    Remove-Item -LiteralPath $backup, $receipt -ErrorAction SilentlyContinue
} catch {
    $detail = $_.Exception.ToString()
    $restored = $false
    if ($replaced) {
        try {
            if ($null -ne $newApp -and -not $newApp.HasExited) {
                # Stop only the updater-owned process and its PyInstaller child.
                $taskkill = Join-Path $env:SystemRoot 'System32/taskkill.exe'
                & $taskkill /PID $newApp.Id /T /F | Out-Null
                if (-not $newApp.WaitForExit(10000)) { throw 'El ejecutable nuevo no se cerró.' }
            }
            $rollbackBy = (Get-Date).AddSeconds(12)
            while (-not $restored) {
                try {
                    [IO.File]::Replace($backup, $target, ($staged + '.failed'))
                    $restored = $true
                } catch {
                    if ((Get-Date) -ge $rollbackBy) { throw }
                    Start-Sleep -Milliseconds 250
                }
            }
            Remove-Item -LiteralPath ($staged + '.failed') -ErrorAction SilentlyContinue
        } catch { $detail += $nl + 'Restauración: ' + $_.Exception.ToString() + $nl + "Copia: $backup" }
    }
    Remove-Item -LiteralPath $staged, $receipt -ErrorAction SilentlyContinue
    $message = "Falló el paso: $step$nl$detail$($nl)Ejecutable: $target"
    try {
        [IO.Directory]::CreateDirectory($logDir) | Out-Null
        [IO.File]::WriteAllText($log, $message)
    } catch {}
    if ($env:JARVIS_UPDATE_TEST -eq '1') {
        [Console]::Error.WriteLine($message)
        exit 1
    }
    Add-Type -AssemblyName PresentationFramework
    $recovery = if ($restored) { 'Se recuperó la versión anterior.' } else { 'Vuelve a abrir JARVIS cuando termine este proceso.' }
    [System.Windows.MessageBox]::Show(
        "No se completó la actualización.$nl$step$nl$recovery$($nl)Detalles guardados en $log",
        "JARVIS"
    ) | Out-Null
    exit 1
}
"""



def acknowledge_startup():
    receipt = os.environ.pop("JARVIS_UPDATE_RECEIPT", None)
    if not receipt:
        return
    temp = None
    try:
        path = Path(receipt)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as output:
            temp = Path(output.name)
            output.write(VERSION)
        temp.replace(path)
    except OSError:
        if temp is not None:
            temp.unlink(missing_ok=True)


VERSION_TAG = re.compile(
    r"v?([0-9]{1,6})\.([0-9]{1,6})\.([0-9]{1,6})(?:\.([0-9]{1,6}))?"
    r"(?:-(alpha|beta|rc)\.([1-9][0-9]{0,5}))?", re.IGNORECASE,
)
STAGES = {"alpha": 0, "beta": 1, "rc": 2, "": 3}
CHANNELS = {"stable": {3}, "experimental": {0, 1, 2, 3}, "beta": {1, 2, 3}, "development": {0, 1, 2, 3}}
POLICY_URL = f"https://raw.githubusercontent.com/{REPO}/dev/0.6.5-universal-apps/assets/release-policy.json"
POLICY_FILE = Path(__file__).resolve().parent / "assets/release-policy.json"
BLOCKED = {"defectuosa", "retirada"}


def version_tuple(tag):
    match = VERSION_TAG.fullmatch(tag) if isinstance(tag, str) else None
    if not match:
        raise ValueError("La versión publicada tiene un formato desconocido.")
    major, minor, patch, revision, name, serial = match.groups()
    return (int(major), int(minor), int(patch), int(revision or 0),
            STAGES[(name or "").lower()], int(serial or 0))


def release_policy(remote=False):
    versions = {}
    sources = [json.loads(POLICY_FILE.read_text(encoding="utf-8"))]
    if remote:
        with urlopen(POLICY_URL, timeout=7) as response:
            sources.append(json.loads(response.read(96 * 1024)))
    for document in sources:
        if document.get("schema") != 1 or not isinstance(document.get("versions"), dict):
            raise ValueError("Registro de versiones no válido.")
        for tag, record in document["versions"].items():
            previous = versions.get(version_tuple(tag), {})
            # A stale remote registry must never reactivate a blocked binary.
            if previous.get("status") not in BLOCKED:
                versions[version_tuple(tag)] = record
    return versions


def select_update(releases, channel, policy, current=VERSION, allow_stable_return=False):
    if channel not in CHANNELS:
        raise ValueError("Canal de actualizaciones desconocido.")
    installed = version_tuple(current)
    current_policy = policy.get(installed, {})
    returning = (allow_stable_return and channel == "stable"
                 and (installed[4] != STAGES[""] or current_policy.get("channel") == "experimental"))
    versions = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = release.get("tag_name")
        try:
            version = version_tuple(tag)
        except ValueError:
            continue
        record = policy.get(version, {})
        if record.get("status") in BLOCKED:
            continue
        stage = version[4]
        prerelease = release.get("prerelease", False)
        if channel == "stable" and (prerelease or record.get("channel") == "experimental"):
            continue
        if channel == "experimental" and stage != STAGES[""] and not prerelease:
            continue
        if stage not in CHANNELS[channel] or version == installed or (version < installed and not returning):
            continue
        for asset in release.get("assets", ()):
            if asset.get("name") != ASSET:
                continue
            digest = asset.get("digest") or ""
            size = asset.get("size")
            if re.fullmatch(r"sha256:[0-9a-f]{64}", digest) and type(size) is int and 0 < size <= MAX_SIZE:
                versions.append((version, tag, digest[7:], size))
                break
    if not versions:
        return None
    return max(versions)[1:]


def latest_update(channel="stable", *, remote_policy=False, allow_stable_return=False):
    policy = release_policy(remote_policy)
    request = Request(
        f"https://api.github.com/repos/{REPO}/releases?per_page=50",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-Updater"},
    )
    with urlopen(request, timeout=10) as response:
        releases = json.loads(response.read(2 * 1024 * 1024))
    return select_update(releases, channel, policy, VERSION, allow_stable_return)


def install_update(update, *, check_policy=False):
    tag, expected_digest, size = update
    version = version_tuple(tag)
    if check_policy and release_policy(remote=True).get(version, {}).get("status") in BLOCKED:
        raise ValueError("Esta versión ha sido bloqueada. Busca otra actualización.")
    target = Path(sys.executable).resolve()
    source = f"https://github.com/{REPO}/releases/download/{tag}/{ASSET}"
    digest = hashlib.sha256()
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".jarvis-update", delete=False) as output:
            staged = Path(output.name)
            length = 0
            with urlopen(source, timeout=20) as download:
                while chunk := download.read(128 * 1024):
                    length += len(chunk)
                    if length > size:
                        raise ValueError("El archivo descargado supera el tamaño publicado.")
                    output.write(chunk)
                    digest.update(chunk)
            if length != size or digest.hexdigest() != expected_digest:
                raise ValueError("La descarga no coincide con la huella SHA-256 publicada.")
        env = dict(os.environ, JARVIS_UPDATE_TARGET=str(target), JARVIS_UPDATE_STAGED=str(staged),
                   JARVIS_UPDATE_PID=str(os.getpid()), JARVIS_UPDATE_EXPECTED=tag.removeprefix("v").removeprefix("V"))
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        helper = subprocess.Popen(
            [str(powershell), "-NoProfile", "-STA", "-EncodedCommand",
             base64.b64encode(INSTALL.encode("utf-16le")).decode("ascii")],
            env=env, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            helper.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return
        raise OSError("Windows cerró el actualizador antes de que pudiera instalar la actualización.")
    except (OSError, ValueError):
        if staged is not None:
            staged.unlink(missing_ok=True)
        raise
