"""Offline keyword spotting and Spanish transcription from mono PCM."""
from dataclasses import dataclass
import json
from pathlib import Path

RATE = 16000
SAMPLE_BYTES = 2
CHUNK_FRAMES = RATE // 20
ASSETS = Path(__file__).resolve().parent / "assets"
MODEL_PATH = ASSETS / "vosk-model-small-es-0.42"
TIMEOUT = 6.0
WAKE_THRESHOLDS = (1e-12, 1e-16, 1e-20, 1e-22, 1e-24)
# Keep a short bounded tail so a command may follow the keyword without a gap.
WAKE_TAIL_BYTES = 2 * RATE * SAMPLE_BYTES
WAKE_RESET_BYTES = 30 * RATE * SAMPLE_BYTES
WAKE_REPLAY_BYTES = RATE * SAMPLE_BYTES


class WakeDetector:
    def __init__(self, sensitivity):
        from pocketsphinx import Decoder, get_model_path

        self.decoder = Decoder(
            hmm=str(Path(get_model_path()) / "en-us" / "en-us"),
            dict=str(ASSETS / "jarvis.dict"),
            lm=None, kws=str(ASSETS / "jarvis.kws"), kws_threshold=WAKE_THRESHOLDS[sensitivity - 1],
            kws_delay=5, loglevel="ERROR", samprate=RATE,
        )
        self.decoder.start_utt()
        self.history = bytearray()
        self.bytes_seen = 0

    def reset(self):
        self.decoder.end_utt()
        self.decoder.start_utt()
        self.history.clear()
        self.bytes_seen = 0

    def feed(self, pcm):
        self.bytes_seen += len(pcm)
        self.history.extend(pcm)
        del self.history[:-WAKE_TAIL_BYTES]
        self.decoder.process_raw(pcm, False, False)
        if self.decoder.hyp():
            last = max(self.decoder.seg(), key=lambda word: word.end_frame)
            # PocketSphinx reports one frame per 10 ms. Keep a little overlap
            # around the word boundary to preserve the start of the next word.
            end = (last.end_frame + 1) * (RATE // 100) * SAMPLE_BYTES
            start = max(0, end - (RATE // 40) * SAMPLE_BYTES)
            offset = max(0, len(self.history) + start - self.bytes_seen)
            return bytes(self.history[offset:])
        if self.bytes_seen >= WAKE_RESET_BYTES:
            # Replay one second at the rollover to catch words across it.
            overlap = bytes(self.history[-WAKE_REPLAY_BYTES:])
            self.reset()
            self.history.extend(overlap)
            self.bytes_seen = len(overlap)
            self.decoder.process_raw(overlap, False, False)
        return None


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float

    @property
    def understood(self):
        return bool(self.text) and self.confidence >= 0.58


class SpanishRecognizer:
    def __init__(self, model):
        from vosk import KaldiRecognizer

        self.recognizer = KaldiRecognizer(model, RATE)
        self.recognizer.SetWords(True)

    def feed(self, pcm):
        if not pcm or not self.recognizer.AcceptWaveform(pcm):
            return None
        result = json.loads(self.recognizer.Result())
        text = result.get("text", "").strip()
        if not text:
            return None
        words = result.get("result", [])
        confidence = sum(word["conf"] for word in words) / len(words) if words else 0.0
        return Transcript(text, confidence)


def spanish_model():
    if not (MODEL_PATH / "am" / "final.mdl").is_file():
        raise OSError("Falta el modelo español. Desde el código, ejecuta python prepare_voice_model.py.")
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    try:
        return Model(str(MODEL_PATH))
    except Exception as error:
        raise OSError("No se pudo inicializar el modelo español.") from error


class Conversation:
    def __init__(self, detector, recognizer, notify):
        self.detector = detector
        self.recognizer = recognizer
        self.notify = notify
        self.active = None
        self.deadline = 0.0

    def reset(self):
        self.active = None
        self.detector.reset()
        self.notify("waiting")

    def feed(self, pcm, now):
        if self.active is None:
            tail = self.detector.feed(pcm)
            if tail is None:
                return None
            self.deadline = now + TIMEOUT
            self.notify("listening")
            self.active = self.recognizer()
            return self.active.feed(tail)
        if now >= self.deadline:
            self.reset()
            return None
        return self.active.feed(pcm)
