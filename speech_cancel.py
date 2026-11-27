"""The only speech accepted during synthesis is a dedicated interruption."""
from dialogue import INTERRUPT_PHRASES
from voice_recognition import SpanishRecognizer


class SpeechCancellation:
    def __init__(self, changed, stopped, capture, model=None, speaker_model=None, authorize=None):
        self.changed = changed
        self.stopped = stopped
        self.capture = capture
        self.authorize = authorize
        grammar = (*INTERRUPT_PHRASES, "[unk]")
        self.recognizer = (SpanishRecognizer(model, grammar, speaker_model=speaker_model)
                           if model and speaker_model else SpanishRecognizer(model, grammar) if model else None)
        self.error = None

    def is_set(self):
        if self.changed.is_set() or self.stopped.is_set():
            return True
        if self.recognizer is None:
            return False
        try:
            for _ in range(32):
                pcm = self.capture.read(timeout=0)
                if pcm is None:
                    break
                result = self.recognizer.feed(pcm)
                if (result and result.confidence >= 0.82 and result.text.casefold() in INTERRUPT_PHRASES
                        and (self.authorize is None or self.authorize(result.speaker))):
                    self.stopped.set()
                    return True
        except (OSError, RuntimeError, ValueError) as error:
            self.error = error
            return True
        return False
