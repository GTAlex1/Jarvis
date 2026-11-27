"""The only speech accepted during synthesis is a dedicated interruption."""
from dialogue import INTERRUPT_PHRASES
from voice_recognition import SpanishRecognizer


class SpeechCancellation:
    def __init__(self, changed, stopped, capture, model=None):
        self.changed = changed
        self.stopped = stopped
        self.capture = capture
        self.recognizer = SpanishRecognizer(model, (*INTERRUPT_PHRASES, "[unk]")) if model else None
        self.error = None

    def is_set(self):
        if self.changed.is_set() or self.stopped.is_set():
            return True
        if self.recognizer is None:
            return False
        try:
            for _ in range(8):
                pcm = self.capture.read(timeout=0)
                if pcm is None:
                    break
                result = self.recognizer.feed(pcm)
                if result and result.confidence >= 0.82 and result.text.casefold() in INTERRUPT_PHRASES:
                    self.stopped.set()
                    return True
        except (OSError, RuntimeError, ValueError) as error:
            self.error = error
            return True
        return False
