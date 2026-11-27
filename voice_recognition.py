"""Offline keyword spotting and Spanish transcription from mono PCM."""
from dataclasses import dataclass
import json
from pathlib import Path

from speakers import VoiceSample

RATE = 16000
SAMPLE_BYTES = 2
CHUNK_FRAMES = RATE // 20
ASSETS = Path(__file__).resolve().parent / "assets"
MODEL_PATH = ASSETS / "vosk-model-small-es-0.42"
SPEAKER_MODEL_PATH = ASSETS / "vosk-model-spk-0.4"
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
        self.activation = b""

    def reset(self):
        self.decoder.end_utt()
        self.decoder.start_utt()
        self.history.clear()
        self.bytes_seen = 0
        self.activation = b""

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
            first = last.start_frame * (RATE // 100) * SAMPLE_BYTES
            begin = max(0, len(self.history) + first - self.bytes_seen)
            self.activation = bytes(self.history[begin:offset])
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
    speaker: VoiceSample | None = None

    @property
    def understood(self):
        return bool(self.text) and self.confidence >= 0.58


class SpanishRecognizer:
    def __init__(self, model, grammar=(), speaker_model=None):
        from vosk import KaldiRecognizer

        args = (json.dumps(grammar),) if grammar else ()
        self.recognizer = KaldiRecognizer(model, RATE, *args)
        self.recognizer.SetWords(True)
        if speaker_model is not None:
            self.recognizer.SetSpkModel(speaker_model)

    def feed(self, pcm):
        if not pcm or not self.recognizer.AcceptWaveform(pcm):
            return None
        return self.transcript(self.recognizer.Result())

    def feed_sample(self, pcm):
        if pcm and self.recognizer.AcceptWaveform(pcm):
            return VoiceSample.from_result(json.loads(self.recognizer.Result()))
        return None

    def finish_sample(self):
        return VoiceSample.from_result(json.loads(self.recognizer.FinalResult()))

    def partial(self):
        return json.loads(self.recognizer.PartialResult()).get("partial", "").strip()

    def finish(self):
        return self.transcript(self.recognizer.FinalResult())

    @staticmethod
    def transcript(encoded):
        result = json.loads(encoded)
        text = result.get("text", "").strip()
        if not text:
            return None
        words = result.get("result", [])
        confidence = sum(word["conf"] for word in words) / len(words) if words else 0.0
        return Transcript(text, confidence, VoiceSample.from_result(result))



@dataclass(frozen=True)
class MicRecognition:
    signal: bool = False
    voice: bool = False
    text: str = ""
    recognized: bool = False

    def status(self):
        signal = "Señal recibida" if self.signal else "Sin señal"
        voice = "Voz detectada" if self.voice else "Voz por detectar"
        words = "Palabras reconocidas" if self.recognized else "Palabras por reconocer"
        return f"{signal} · {voice} · {words}"


class RecognitionProbe:
    """Track level, speech activity and Spanish hypotheses independently."""
    def __init__(self, recognizer):
        from pocketsphinx import Vad

        self.recognizer = recognizer
        self.vad = Vad(2, RATE, 0.03)
        self.buffer = bytearray()
        self.speech_frames = 0
        self.heard_voice = False
        self.heard_signal = False
        self.words = []
        self.recognized = False

    def feed(self, pcm, amplitude):
        self.heard_signal |= amplitude >= 33  # roughly -60 dBFS
        self.buffer.extend(pcm)
        size = self.vad.frame_bytes
        end = len(self.buffer) // size * size
        for start in range(0, end, size):
            if self.vad.is_speech(bytes(self.buffer[start:start + size])):
                self.speech_frames += 1
                self.heard_voice |= self.speech_frames >= 3
            else:
                self.speech_frames = 0
        del self.buffer[:end]
        self.add(self.recognizer.feed(pcm))
        return self.snapshot(self.recognizer.partial())

    def add(self, transcript):
        if transcript:
            self.words.append(transcript.text)
            self.recognized |= transcript.understood

    def snapshot(self, partial=""):
        text = " ".join((*self.words, partial)).strip()
        return MicRecognition(self.heard_signal, self.heard_voice, text[-240:], self.recognized)

    def finish(self):
        self.add(self.recognizer.finish())
        return self.snapshot()

def spanish_model():
    if not (MODEL_PATH / "am" / "final.mdl").is_file():
        raise OSError("Falta el modelo español. Desde el código, ejecuta python prepare_voice_model.py.")
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    try:
        return Model(str(MODEL_PATH))
    except Exception as error:
        raise OSError("No se pudo inicializar el modelo español.") from error


def local_speaker_model():
    from vosk import SetLogLevel, SpkModel

    SetLogLevel(-1)
    if not (SPEAKER_MODEL_PATH / "final.ext.raw").is_file():
        raise OSError("Falta el modelo local de verificación de voz.")
    try:
        return SpkModel(str(SPEAKER_MODEL_PATH))
    except Exception as error:
        raise OSError("No se pudo iniciar la verificación de voz.") from error


class Conversation:
    def __init__(self, detector, recognizer, notify):
        self.detector = detector
        self.recognizer = recognizer
        self.notify = notify
        self.active = None
        self.deadline = 0.0
        self.following = False
        self.audio = bytearray()
        self.activation = b""

    def listen_for_reply(self, now, seconds):
        self.active = self.recognizer()
        self.audio.clear()
        self.activation = b""
        self.deadline = now + seconds
        self.following = True
        self.notify("followup")

    def reset(self, notify=True):
        self.active = None
        self.following = False
        self.detector.reset()
        self.audio.clear()
        self.activation = b""
        if notify:
            self.notify("waiting")

    def feed(self, pcm, now):
        if self.active is None:
            tail = self.detector.feed(pcm)
            if tail is None:
                return None
            self.deadline = now + TIMEOUT
            self.notify("listening")
            self.active = self.recognizer()
            self.audio[:] = tail
            activation = self.detector.activation
            self.activation = activation if isinstance(activation, bytes) else b""
            return self.active.feed(tail)
        if now >= self.deadline:
            self.reset()
            return None
        self.audio.extend(pcm)
        # Bound a pathological streaming utterance and split follow-up turns
        # after their endpoint so a prior speaker never feeds later decisions.
        del self.audio[:-int(10 * RATE * SAMPLE_BYTES)]
        return self.active.feed(pcm)
