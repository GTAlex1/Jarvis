"""Offline keyword spotting and Spanish transcription from mono PCM."""
from dataclasses import dataclass, replace
import json

from speakers import VoiceSample

from wake_word import ASSETS, CHUNK_FRAMES, RATE, SAMPLE_BYTES, WakeDetector

MODEL_PATH = ASSETS / "vosk-model-small-es-0.42"
SPEAKER_MODEL_PATH = ASSETS / "vosk-model-spk-0.4"
TIMEOUT = 6.0


@dataclass(frozen=True)
class Transcript:
    text: str
    confidence: float
    speaker: VoiceSample | None = None
    words: tuple = ()

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
        timings = tuple((word["word"], word["start"], word["end"], word["conf"]) for word in words
                        if {"word", "start", "end"} <= word.keys())
        return Transcript(text, confidence, VoiceSample.from_result(result), timings)



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


def decode_buffer(model, pcm, grammar):
    decoder = SpanishRecognizer(model, grammar)
    step = CHUNK_FRAMES * SAMPLE_BYTES
    audio = bytes(RATE * SAMPLE_BYTES // 4) + pcm + bytes(RATE * SAMPLE_BYTES)
    found = []
    for offset in range(0, len(audio), step):
        if result := decoder.feed(audio[offset:offset + step]):
            found.append(result)
    if result := decoder.finish():
        found.append(result)
    return found


def corroborate_wake(model, pcm, sensitivity):
    evidence = decode_buffer(model, pcm, ("jarvis", "[unk]"))
    if not evidence or not evidence[0].words:
        return None
    word, start, end, score = evidence[0].words[0]
    minimum = (0.98, 0.94, 0.88, 0.82, 0.76)[sensitivity - 1]
    if word != "jarvis" or score < minimum or end - start < 0.16:
        return None
    return min(len(pcm), max(0, round((end - 0.25) * RATE) * SAMPLE_BYTES))


def safe_redecode(model, pcm):
    """A bounded grammar rescues only two benign built-in intents."""
    allowed = ("ayuda", "dime como puedes ayudarme", "abre calculadora",
               "abre la calculadora", "abre la calculadora de windows")
    alternatives = ("jarvis", "[unk]", "no", "no abras la calculadora", "no abre la calculadora",
                    "si abre la calculadora", "cuando abre la calculadora", "dijo abre la calculadora")
    results = decode_buffer(model, pcm, (*allowed, *alternatives))
    if not results or len(results) > 2:
        return None
    words = tuple(word for result in results for word in result.words)
    text = " ".join(word[0] for word in words)
    if text not in {"jarvis " + phrase for phrase in allowed} or min(word[3] for word in words) < 0.82:
        return None
    result = results[-1]
    # The prepended silence is artificial. Rebase metadata to the captured PCM.
    words = tuple((word, max(0, start - 0.25), max(0, end - 0.25), conf)
                  for word, start, end, conf in words[1:])
    return replace(result, text=" ".join(word[0] for word in words), words=words)


class Conversation:
    def __init__(self, detector, recognizer, notify, recover=None):
        self.detector = detector
        self.recognizer = recognizer
        self.notify = notify
        self.recover = recover
        self.active = None
        self.deadline = 0.0
        self.following = False
        self.audio = bytearray()
        self.activation = b""
        self.boundary = 0

    def listen_for_reply(self, now, seconds):
        self.active = self.recognizer()
        self.audio.clear()
        self.activation = b""
        self.boundary = 0
        self.deadline = now + seconds
        self.following = True
        self.notify("followup")

    def reset(self, notify=True):
        self.active = None
        self.following = False
        self.detector.reset()
        self.audio.clear()
        self.activation = b""
        self.boundary = 0
        if notify:
            self.notify("waiting")

    def resolved(self, transcript, timeout=False):
        from command_language import normalize_order
        from commands import parse

        primary = self.command_text(transcript)
        if not self.activation or self.recover is None:
            return primary
        if primary and parse(normalize_order(primary.text)):
            return primary
        # Do not rescore over an observed negation, quote or condition.
        if primary and not normalize_order(primary.text):
            return primary
        if primary is None and not timeout:
            return None
        beginning = self.activation[:-self.boundary] if self.boundary else self.activation
        revision = self.recover(beginning + bytes(self.audio))
        if revision:
            offset = len(beginning) / (RATE * SAMPLE_BYTES)
            if revision.words[0][1] < offset - 0.12:
                return primary
            words = tuple((word, max(0, start - offset), max(0, end - offset), conf)
                          for word, start, end, conf in revision.words)
            return replace(revision, words=words)
        return primary

    def command_text(self, transcript):
        if not transcript or not self.boundary or not transcript.words:
            return transcript
        # The overlap can yield a leftover syllable of the activation. Drop
        # only known wake tokens in this region and keep the first command word.
        words = transcript.words
        marker = self.boundary / (RATE * SAMPLE_BYTES)
        while words and words[0][0] in {"jarvis", "yarvis", "harvis", "yates", "gris"} and words[0][2] <= marker + 0.13:
            words = words[1:]
        if not words:
            return None
        return replace(transcript, text=" ".join(word[0] for word in words), words=words,
                       confidence=sum(word[3] for word in words) / len(words))

    def speaker_audio(self, transcript, include_cue=False):
        if not transcript.words:
            return bytes(self.audio[self.boundary:]), self.activation if include_cue else b""
        step = RATE * SAMPLE_BYTES
        first, last = transcript.words[0][1], transcript.words[-1][2]
        start = max(0, round((first - 0.10) * RATE) * SAMPLE_BYTES)
        end = min(len(self.audio), round((last + 0.10) * RATE) * SAMPLE_BYTES)
        # Separate captured parts exactly. Do not mix other voiced segments
        # in the same buffer or double count the overlap during verification.
        start = max(0, min(start, end))
        split = max(start, min(self.boundary, end))
        if not include_cue:
            return bytes(self.audio[split:end]), b""
        if start < self.boundary:
            activation = self.activation[:-(self.boundary - start)]
            return bytes(self.audio[start:end]), activation
        activation = self.activation if start - self.boundary <= step * 0.16 else b""
        return bytes(self.audio[split:end]), activation

    def feed(self, pcm, now):
        if self.active is None:
            tail = self.detector.feed(pcm)
            if tail is None:
                return None
            self.deadline = now + TIMEOUT
            self.notify("listening")
            self.active = self.recognizer()
            self.audio[:] = tail
            activation, boundary = self.detector.activation, getattr(self.detector, "boundary", 0)
            self.activation = activation if isinstance(activation, bytes) else b""
            self.boundary = boundary if isinstance(boundary, int) else 0
            return self.resolved(self.active.feed(tail))
        if now >= self.deadline:
            if self.activation and self.recover and (last := self.resolved(self.active.finish(), timeout=True)):
                return last
            self.reset()
            return None
        available = max(0, 10 * RATE * SAMPLE_BYTES - len(self.audio))
        pcm = pcm[:available]
        self.audio.extend(pcm)
        return self.resolved(self.active.feed(pcm))
