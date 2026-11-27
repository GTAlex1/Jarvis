"""Local speaker verification and profile serialization, independent of Windows."""
from dataclasses import dataclass
import json
from math import isfinite, sqrt
from uuid import uuid4

DIMENSIONS = 128
SAMPLES_REQUIRED = 3
MAX_PROFILES = 20
MIN_FRAMES = 50
ENROLLMENT_FRAMES = 110


def unit(vector):
    if not isinstance(vector, (list, tuple)) or len(vector) != DIMENSIONS:
        return None
    if any(type(n) not in (int, float) or not isfinite(n) or abs(n) > 1e6 for n in vector):
        return None
    length = sqrt(sum(n * n for n in vector))
    return tuple(n / length for n in vector) if length > 0 else None


def cosine(first, second):
    return sum(a * b for a, b in zip(first, second))


@dataclass(frozen=True)
class VoiceSample:
    vector: tuple
    frames: int

    @classmethod
    def from_result(cls, result):
        vector = unit(result.get("spk"))
        frames = result.get("spk_frames", 0)
        if vector is not None and type(frames) is int and MIN_FRAMES <= frames <= 3000:
            return cls(vector, frames)
        return None


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    samples: tuple

    @classmethod
    def enroll(cls, name, samples):
        if len(samples) != SAMPLES_REQUIRED or any(sample.frames < ENROLLMENT_FRAMES for sample in samples):
            raise ValueError("Graba tres muestras con al menos un segundo de voz continua cada una.")
        vectors = tuple(unit(sample.vector) for sample in samples)
        if not all(vectors):
            raise ValueError("Alguna muestra de voz no es válida.")
        if min(cosine(a, b) for i, a in enumerate(vectors) for b in vectors[i + 1:]) < 0.45:
            raise ValueError("Las muestras son demasiado distintas. Repítelas con la misma voz y micrófono.")
        return cls(uuid4().hex, profile_name(name), vectors)

    def score(self, vector):
        scores = sorted((cosine(item, vector) for item in self.samples), reverse=True)
        return (scores[0] + scores[1]) / 2


def profile_name(name):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or not name.strip().isprintable():
        raise ValueError("Escribe un nombre de perfil de 1 a 60 caracteres.")
    return name.strip()


def identify(sample, profiles, threshold, expected=None):
    if not isinstance(sample, VoiceSample) or sample.frames < MIN_FRAMES:
        return None
    vector = unit(sample.vector)
    if vector is None:
        return None
    candidates = sorted(((profile.score(vector), profile.id) for profile in profiles), reverse=True)
    if not candidates:
        return None
    score, identity = candidates[0]
    if score < threshold or (expected is not None and identity != expected):
        return None
    if len(candidates) > 1 and score - candidates[1][0] < 0.035:
        return None
    return identity


def encode_profiles(profiles):
    return json.dumps({"version": 1, "model": "vosk-spk-0.4",
                       "profiles": [{"id": p.id, "name": p.name, "samples": p.samples} for p in profiles]},
                      ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def decode_profiles(data):
    saved = json.loads(data)
    if not isinstance(saved, dict) or saved.get("version") != 1 or saved.get("model") != "vosk-spk-0.4":
        raise ValueError("Formato de perfiles de voz desconocido.")
    records = saved.get("profiles")
    if not isinstance(records, list) or len(records) > MAX_PROFILES:
        raise ValueError("Lista de perfiles de voz inválida.")
    profiles = []
    identifiers = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Perfil de voz inválido.")
        identifier = record.get("id")
        vectors = record.get("samples")
        if (not isinstance(identifier, str) or len(identifier) != 32 or
                any(ch not in "0123456789abcdef" for ch in identifier) or identifier in identifiers or
                not isinstance(vectors, list) or len(vectors) != SAMPLES_REQUIRED):
            raise ValueError("Perfil de voz inválido.")
        samples = tuple(unit(vector) for vector in vectors)
        if not all(samples):
            raise ValueError("Muestra de voz inválida.")
        identifiers.add(identifier)
        profiles.append(Profile(identifier, profile_name(record.get("name")), samples))
    return tuple(profiles)
