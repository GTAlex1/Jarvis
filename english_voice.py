"""Optional, verified English acoustic model. Speech itself is processed offline."""
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

MODEL = "vosk-model-small-en-us-0.15"
URL = f"https://alphacephei.com/vosk/models/{MODEL}.zip"
SIZE = 41205931
DIGEST = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"


def model_path():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "JARVIS" / "models" / MODEL


def installed():
    return (model_path() / ".jarvis-verified").is_file() and (model_path() / "am/final.mdl").is_file()


def install():
    if installed():
        return
    path = model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(URL, timeout=30) as response:
        archive = response.read(SIZE + 1)
    if len(archive) != SIZE or sha256(archive).hexdigest() != DIGEST:
        raise OSError("La descarga del modelo inglés no coincide con la huella esperada.")
    with tempfile.TemporaryDirectory(dir=path.parent) as staging:
        with ZipFile(BytesIO(archive)) as verified:
            verified.extractall(staging)  # The complete archive was pinned and verified above.
        candidate = Path(staging) / MODEL
        if not (candidate / "am/final.mdl").is_file():
            raise OSError("La descarga no contiene el modelo acústico.")
        (candidate / ".jarvis-verified").write_text(DIGEST, encoding="ascii")
        if not installed():
            if path.exists():
                raise OSError(f"Hay un modelo incompleto en {path}. Elimina esa carpeta y reinténtalo.")
            candidate.rename(path)


def load():
    if not installed():
        raise OSError("El modelo inglés todavía no está preparado. Elige «Voz en inglés…» en la bandeja.")
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    return Model(str(model_path()))
