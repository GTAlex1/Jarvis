"""Fetch the pinned Spanish Vosk model for a source checkout or Windows build."""
from hashlib import sha256
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile

from voice_recognition import MODEL_PATH

URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
SIZE = 39817833
SHA256 = "09b239888f633ef2f0b4e09736e3d9936acfd810bc65d53fad45261762c6511f"


def main():
    with urlopen(URL, timeout=30) as response:
        archive = response.read(SIZE + 1)
    if len(archive) != SIZE or sha256(archive).hexdigest() != SHA256:
        raise SystemExit("El modelo de voz no coincide con el tamaño y SHA-256 esperados.")
    with ZipFile(BytesIO(archive)) as model:
        model.extractall(MODEL_PATH.parent)
    print(f"Modelo español disponible en {MODEL_PATH}")


if __name__ == "__main__":
    main()
