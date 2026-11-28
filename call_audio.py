"""Conservative quality gate for audio overlapping Windows playback."""
from collections import deque
import re
from unicodedata import normalize, combining


def playback_input(name):
    key = "".join(ch for ch in normalize("NFD", name.casefold()) if not combining(ch))
    return bool(re.search(r"\b(?:stereo mix|mezcla estereo|stereo mixer|stereo loopback|"
                          r"what u hear|what you hear|wave out mix|mixagem estereo)\b|"
                          r"\[loopback\]", key))


class PlaybackActivity:
    def __init__(self, meter=None):
        self.meter = meter
        self.next_read = 0.0
        self.recent = deque(maxlen=20)

    def observe(self, now):
        if self.meter and now >= self.next_read:
            self.next_read = now + 0.15
            try:
                peak = self.meter()
            except OSError:
                peak = None
            if peak is not None:
                self.recent.append((now, peak))

    def overlapped(self, now):
        # Two readings over the threshold avoid using a sole click as evidence.
        return sum(peak >= 0.035 for instant, peak in self.recent if now - instant <= 1.15) >= 2


def contaminated(transcript, playback, confirmation=False):
    """Playback activity is a risk signal, never a speaker identification."""
    if not playback:
        return False
    threshold = 0.86 if confirmation else 0.78
    minimum = 0.65 if confirmation else 0.52
    return (transcript.confidence < threshold
            or any(word[3] < minimum for word in transcript.words))
