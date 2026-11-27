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

VERSION = "0.4.0"
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
$replaced = $false
try {
    Wait-Process -Id ([int]$env:JARVIS_UPDATE_PID) -Timeout 30 -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 50; $i++) {
        try {
            [IO.File]::Replace($staged, $target, $backup)
            $replaced = $true
            break
        } catch [IO.IOException] {
            if ($i -eq 49) { throw }
            Start-Sleep -Milliseconds 200
        }
    }
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target) -ErrorAction Stop
    Remove-Item -LiteralPath $backup -ErrorAction SilentlyContinue
} catch {
    if ($replaced) {
        try { [IO.File]::Replace($backup, $target, $null) } catch {}
    }
    Remove-Item -LiteralPath $staged -ErrorAction SilentlyContinue
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "No se pudo aplicar la actualización. Vuelve a abrir JARVIS o descarga la versión desde GitHub Releases.",
        "JARVIS"
    ) | Out-Null
}
"""


def version_tuple(tag):
    if not re.fullmatch(r"v?\d{1,6}\.\d{1,6}\.\d{1,6}", tag):
        raise ValueError("La versión publicada tiene un formato desconocido.")
    return tuple(map(int, tag.removeprefix("v").split(".")))


def latest_update():
    request = Request(
        f"https://api.github.com/repos/{REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-Updater"},
    )
    with urlopen(request, timeout=10) as response:
        release = json.loads(response.read(512 * 1024))
    tag = release["tag_name"]
    if version_tuple(tag) <= version_tuple(VERSION):
        return None
    for asset in release["assets"]:
        if asset["name"] != ASSET:
            continue
        digest = asset.get("digest") or ""
        size = asset["size"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not 0 < size <= MAX_SIZE:
            raise ValueError("GitHub no proporciona una huella SHA-256 válida para esta descarga.")
        return tag, digest[7:], size
    raise ValueError("La nueva versión todavía no contiene JARVIS.exe.")


def install_update(update):
    tag, expected_digest, size = update
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
                   JARVIS_UPDATE_PID=str(os.getpid()))
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        subprocess.Popen(
            [str(powershell), "-NoProfile", "-STA", "-EncodedCommand",
             base64.b64encode(INSTALL.encode("utf-16le")).decode("ascii")],
            env=env, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, ValueError):
        if staged is not None:
            staged.unlink(missing_ok=True)
        raise
