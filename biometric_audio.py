"""Quality and bounded speaker extraction from the same mono PCM in both flows."""
from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from speakers import MIN_FRAMES, identify
from voice_recognition import CHUNK_FRAMES, RATE, SAMPLE_BYTES, SpanishRecognizer


class Reason(str, Enum):
    ACCEPTED = "autorizada"
    UNAUTHORIZED = "no_autorizada"
    SHORT = "muestra_corta"
    SILENCE = "silencio"
    NOISE = "ruido"
    CLIPPING = "saturacion"
    ERROR = "error_verificacion"
    MISSING = "sin_perfil"
    DAMAGED = "perfil_invalido"


MESSAGES = {
    Reason.UNAUTHORIZED: "La voz no coincide con un perfil autorizado.",
    Reason.SHORT: "Necesito más voz. Repite la orden usando una frase completa.",
    Reason.SILENCE: "No se detectó voz. Comprueba el micrófono y vuelve a hablar.",
    Reason.NOISE: "Hay demasiado ruido de fondo para verificar la voz.",
    Reason.CLIPPING: "El audio se satura. Aléjate un poco del micrófono o reduce la ganancia.",
    Reason.ERROR: "Falló la verificación local. Consulta el diagnóstico de voz.",
    Reason.MISSING: "Registra un perfil antes de activar la verificación.",
    Reason.DAMAGED: "El perfil no se puede leer. Comprueba o renueva los perfiles de voz.",
}


@dataclass(frozen=True)
class Reading:
    reason: Reason | None
    voiced_ms: int = 0
    peak_percent: int = 0
    sample: object = None

    def message(self):
        info = MESSAGES.get(self.reason, "Calidad adecuada")
        return f"{info} · {self.voiced_ms} ms de voz · pico {self.peak_percent} %"


def frame_levels(pcm):
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    size = RATE * 30 // 1000
    frames = samples[:len(samples) // size * size].reshape(-1, size)
    return samples, np.sqrt(np.mean(frames * frames, axis=1))


def contiguous(activation, command):
    """Borrow the wake word only across one uninterrupted acoustic turn."""
    if not activation or not command:
        return False
    _, before = frame_levels(activation)
    _, after = frame_levels(command[:RATE * SAMPLE_BYTES // 2])
    last, first = np.flatnonzero(before >= 120), np.flatnonzero(after >= 120)
    return bool(len(last) and len(first) and len(before) - 1 - last[-1] + first[0] <= 5)


def quality(pcm):
    from pocketsphinx import Vad

    samples, levels = frame_levels(pcm)
    if not len(levels):
        return Reading(Reason.SHORT)
    peak = min(100, round(float(np.max(np.abs(samples))) * 100 / 32768))
    if np.mean(np.abs(samples) >= 32600) > 0.006:
        return Reading(Reason.CLIPPING, peak_percent=peak)
    if np.max(levels) < 45:
        return Reading(Reason.SILENCE, peak_percent=peak)
    vad = Vad(2, RATE, 0.03)
    size = vad.frame_bytes
    voice = np.array([vad.is_speech(pcm[i * size:(i + 1) * size]) for i in range(len(levels))])
    duration = int(np.sum(voice & (levels >= 60))) * 30
    floor, top = np.percentile(levels, (20, 90))
    if floor > 350 and top < floor * 2.3:
        return Reading(Reason.NOISE, duration, peak)
    if duration < 120:
        return Reading(Reason.NOISE if floor > 100 else Reason.SHORT, duration, peak)
    return Reading(None, duration, peak)


def extract(model, speaker_model, pcm, minimum=MIN_FRAMES):
    reading = quality(pcm)
    if reading.reason:
        return reading
    # Feed in the same increments as live decoding. Vosk removes silence on
    # the decoded alignment. One AcceptWaveform over the whole block differs.
    step = CHUNK_FRAMES * SAMPLE_BYTES
    audio = bytes(RATE * SAMPLE_BYTES // 2) + pcm + bytes(RATE * SAMPLE_BYTES)
    decoder = SpanishRecognizer(model, speaker_model=speaker_model)
    best = None
    for offset in range(0, len(audio), step):
        if item := decoder.feed_sample(audio[offset:offset + step]):
            if best is None or item.frames > best.frames:
                best = item
    final = decoder.finish_sample()
    if final and (best is None or final.frames > best.frames):
        best = final
    if best is None or best.frames < minimum:
        return replace(reading, reason=Reason.SHORT)
    return replace(reading, sample=best)


def verify(lookup, command, activation, profiles, threshold, expected=None):
    """A sufficient command is scored alone, even when a wake word is present."""
    if not profiles:
        return Reason.MISSING, None
    try:
        reading = lookup(command)
        if reading.reason == Reason.SHORT and reading.voiced_ms >= 210 and contiguous(activation, command):
            reading = lookup(activation + command)
    except (OSError, ValueError, RuntimeError, ImportError):
        return Reason.ERROR, None
    if reading.reason is not None:
        return reading.reason, None
    owner = identify(reading.sample, profiles, threshold, expected)
    return (Reason.ACCEPTED, owner) if owner else (Reason.UNAUTHORIZED, None)
