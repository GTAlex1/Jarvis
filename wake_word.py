"""Local wake-word detector. A match opens transcription, never authorization."""
from collections import deque
from dataclasses import dataclass
from pathlib import Path

RATE = 16000
SAMPLE_BYTES = 2
CHUNK_FRAMES = RATE // 20
BYTES_PER_SECOND = RATE * SAMPLE_BYTES
ASSETS = Path(__file__).resolve().parent / "assets"
WAKE_WORD = "Jarvis"


@dataclass(frozen=True)
class WakeModel:
    dictionary: Path
    keywords: Path


DEFAULT_MODEL = WakeModel(ASSETS / "jarvis.dict", ASSETS / "jarvis.kws")
WAKE_THRESHOLDS = (1e-12, 1e-16, 1e-20, 1e-22, 1e-24)
HISTORY_BYTES = 2 * BYTES_PER_SECOND
RESET_BYTES = 30 * BYTES_PER_SECOND
OVERLAP_BYTES = BYTES_PER_SECOND * 3 // 20


class VoiceActivity:
    def __init__(self):
        from pocketsphinx import Vad

        self.vad = Vad(2, RATE, 0.03)
        self.frames = deque(maxlen=70)
        self.buffer = bytearray()
        self.offset = 0

    def reset(self):
        self.frames.clear()
        self.buffer.clear()
        self.offset = 0

    def feed(self, pcm):
        self.buffer.extend(pcm)
        size = self.vad.frame_bytes
        end = len(self.buffer) // size * size
        for start in range(0, end, size):
            speech = self.vad.is_speech(bytes(self.buffer[start:start + size]))
            self.frames.append((self.offset, speech))
            self.offset += size
        del self.buffer[:end]

    def opening(self, begin, end, weak):
        """Locate the voiced segment that contains the keyword hypothesis."""
        voiced = [offset for offset, speech in self.frames if speech and offset < end]
        if len(voiced) < 3:
            return None
        onset = voiced[0]
        for before, after in zip(voiced, voiced[1:]):
            if after - before > 0.18 * BYTES_PER_SECOND:
                onset = after
        tolerance = (0.50 if weak else 0.24) * BYTES_PER_SECOND
        if begin - tolerance <= onset <= begin + 0.12 * BYTES_PER_SECOND:
            return onset
        return None


class WakeDetector:
    def __init__(self, sensitivity, model=DEFAULT_MODEL, corroborate=None):
        from pocketsphinx import Decoder, get_model_path

        self.decoder = Decoder(
            hmm=str(Path(get_model_path()) / "en-us" / "en-us"),
            dict=str(model.dictionary), lm=None, kws=str(model.keywords),
            kws_threshold=WAKE_THRESHOLDS[sensitivity - 1], kws_delay=5, loglevel="ERROR", samprate=RATE,
        )
        self.decoder.start_utt()
        self.corroborate = corroborate
        self.sensitivity = sensitivity
        self.activity = VoiceActivity()
        self.history = bytearray()
        self.bytes_seen = 0
        self.activation = b""
        self.boundary = 0
        self.weak = False
        self.processed_match = -1

    def reset(self):
        self.decoder.end_utt()
        self.decoder.start_utt()
        self.activity.reset()
        self.history.clear()
        self.bytes_seen = 0
        self.activation = b""
        self.boundary = 0
        self.weak = False
        self.processed_match = -1

    def append(self, pcm):
        self.bytes_seen += len(pcm)
        self.history.extend(pcm)
        del self.history[:-HISTORY_BYTES]
        self.activity.feed(pcm)
        self.decoder.process_raw(pcm, False, False)

    def feed(self, pcm):
        self.append(pcm)
        scale = (RATE // 100) * SAMPLE_BYTES
        if self.decoder.hyp():
            candidates = [word for word in self.decoder.seg() if word.start_frame > self.processed_match]
            strong = [word for word in candidates if word.word in {"jarvis", "jarviss"}]
            weak = [word for word in candidates if word.word not in {"jarvis", "jarviss"}]
            # Prefer the standard keyword. Variants require a second lexical cue.
            for word in sorted(strong, key=lambda item: -item.end_frame):
                begin, end = word.start_frame * scale, (word.end_frame + 1) * scale
                if self.activity.opening(begin, end, False) is not None:
                    return self.cut(begin, end, False)
            for word in sorted(weak, key=lambda item: (item.end_frame, -item.prob)):
                begin, end = word.start_frame * scale, (word.end_frame + 1) * scale
                if self.bytes_seen - end < int(0.11 * BYTES_PER_SECOND):
                    break
                onset = self.activity.opening(begin, end, True)
                if self.corroborate is not None and onset is not None:
                    origin = self.bytes_seen - len(self.history)
                    start = max(0, onset - int(0.14 * BYTES_PER_SECOND) - origin)
                    stop = min(len(self.history), end + int(0.11 * BYTES_PER_SECOND) - origin)
                    evidence_end = self.corroborate(bytes(self.history[start:stop]), self.sensitivity)
                    if evidence_end is not None:
                        return self.cut(origin + start, origin + start + evidence_end, True)
                self.processed_match = max(self.processed_match, word.start_frame + 5)
            if strong and not weak:
                self.processed_match = max(word.start_frame for word in strong) + 5
        if self.bytes_seen >= RESET_BYTES:
            overlap = bytes(self.history[-BYTES_PER_SECOND:])
            self.reset()
            self.append(overlap)
        return None


    def cut(self, begin, end, weak):
        origin = self.bytes_seen - len(self.history)
        split = min(len(self.history), max(0, end - origin))
        # Retain the original alignment for standard KWS results. The
        # timestamp from the independent Spanish check can miss a syllable.
        overlap = OVERLAP_BYTES if weak else BYTES_PER_SECOND // 40
        before = max(0, split - overlap)
        self.activation = bytes(self.history[max(0, begin - origin):split])
        self.boundary = split - before
        self.weak = weak
        return bytes(self.history[before:])
