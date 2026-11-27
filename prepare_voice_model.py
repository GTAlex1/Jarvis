"""Fetch and verify the pinned local speech and speaker models."""
from hashlib import sha256
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile

from voice_recognition import MODEL_PATH, SPEAKER_MODEL_PATH

MODELS = (
    (MODEL_PATH, 39817833, "09b239888f633ef2f0b4e09736e3d9936acfd810bc65d53fad45261762c6511f"),
    (SPEAKER_MODEL_PATH, 13869103, "a74d8f51144484813e16af689bb0f916b7a111e2347f467c4933c1166097b5a7"),
)


def main():
    for path, size, digest in MODELS:
        url = f"https://alphacephei.com/vosk/models/{path.name}.zip"
        with urlopen(url, timeout=45) as response:
            archive = response.read(size + 1)
        if len(archive) != size or sha256(archive).hexdigest() != digest:
            raise SystemExit(f"El modelo {path.name} no coincide con el tamaño y SHA-256 esperados.")
        with ZipFile(BytesIO(archive)) as model:
            model.extractall(path.parent)
        print(f"Modelo local disponible en {path}")


if __name__ == "__main__":
    main()
