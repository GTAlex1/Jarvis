"""Run the voice loop independently of the Tk event loop and command worker."""
from concurrent.futures import TimeoutError
from queue import Empty, SimpleQueue
from threading import Event, Thread
from time import monotonic

from preferences import VoiceSettings
from voice_audio import Microphone, input_devices, installed_voices, speak
from voice_recognition import Conversation, SpanishRecognizer, WakeDetector, spanish_model

STATE_LABELS = {
    "disabled": "Escucha permanente desactivada",
    "muted": "Micrófono desactivado",
    "starting": "Preparando micrófono",
    "waiting": "En espera · di «Jarvis»",
    "listening": "Escuchando la orden",
    "processing": "Procesando voz",
    "executing": "Ejecutando la orden",
    "speaking": "Respondiendo",
    "unavailable": "Micrófono o voz no disponible",
}
ERRORS = (ImportError, OSError, RuntimeError, ValueError)
RETRY_SECONDS = 3
MODEL_IDLE_SECONDS = 30
PLAYBACK_GUARD_SECONDS = 0.45


class VoiceService:
    def __init__(self, submit, on_state, on_catalog):
        self.submit = submit
        self.on_state = on_state
        self.on_catalog = on_catalog
        self.changed = Event()
        self.stopped = Event()
        self.catalog = SimpleQueue()
        self.config = VoiceSettings(), True
        self.thread = None
        self.last_state = None
        self.model = None
        self.model_used = 0.0

    def start(self):
        if self.thread is None:
            self.thread = Thread(target=self.run, name="jarvis-voice", daemon=True)
            self.thread.start()

    def configure(self, settings, microphone):
        config = (settings, microphone)
        if config != self.config:
            self.config = config
            self.changed.set()
        if settings.enabled and microphone:
            self.start()
        elif self.thread is None:
            self.notify("disabled" if microphone else "muted")

    def refresh_catalog(self):
        self.catalog.put(None)
        self.changed.set()
        self.start()

    def close(self):
        self.stopped.set()
        self.changed.set()
        if self.thread is not None:
            self.thread.join(timeout=4)

    def notify(self, state, detail=""):
        event = (state, detail)
        if not self.stopped.is_set() and event != self.last_state:
            self.last_state = event
            self.on_state(*event)

    def recognize(self):
        if self.model is None:
            self.model = spanish_model()
        self.model_used = monotonic()
        return SpanishRecognizer(self.model)

    def list_options(self):
        try:
            self.catalog.get_nowait()
        except Empty:
            return
        while True:
            try:
                self.catalog.get_nowait()
            except Empty:
                break
        devices, voices, errors = [], [], []
        try:
            devices = input_devices(refresh=True)
        except ERRORS as error:
            errors.append(f"Micrófonos: {error}")
        try:
            voices = installed_voices(self.changed)
        except ERRORS as error:
            errors.append(f"Voces: {error}")
        self.on_catalog(devices, voices, "\n".join(errors))

    def run(self):
        while not self.stopped.is_set():
            self.changed.clear()
            if self.stopped.is_set():
                break
            settings, microphone = self.config
            self.list_options()
            if not settings.enabled or not microphone:
                self.model = None
                self.notify("disabled" if microphone else "muted")
                self.changed.wait()
                continue
            if self.changed.is_set():
                continue
            try:
                self.notify("starting")
                devices = input_devices(refresh=True)
                detector = WakeDetector(settings.sensitivity)
                with Microphone(devices, settings.device) as capture:
                    self.listen(capture, detector, settings)
            except ERRORS as error:
                self.model = None
                detail = ("Instala las dependencias de voz indicadas en el README."
                          if isinstance(error, ImportError) else str(error))
                self.notify("unavailable", detail)
                self.changed.wait(RETRY_SECONDS)
            finally:
                if self.stopped.is_set():
                    self.model = None

    def listen(self, capture, detector, settings):
        exchange = Conversation(detector, self.recognize, self.notify)
        self.notify("waiting")
        while not self.changed.is_set():
            pcm = capture.read()
            now = monotonic()
            if pcm is None:
                continue
            if exchange.active is None and now - self.model_used > MODEL_IDLE_SECONDS:
                self.model = None
            transcript = exchange.feed(pcm, now)
            if transcript is None or self.changed.is_set():
                continue
            self.notify("processing")
            capture.pause()
            warning = self.respond(transcript, settings)
            if self.changed.wait(PLAYBACK_GUARD_SECONDS):
                return
            capture.resume()
            exchange.reset()
            if warning:
                self.notify("waiting", warning)

    def respond(self, transcript, settings):
        if transcript.understood:
            self.notify("executing")
            reply = self.submit(transcript.text)
            while not self.changed.is_set():
                try:
                    text = reply.result(timeout=0.2)
                except TimeoutError:
                    continue
                except Exception as error:
                    text = f"No pude completar la orden. {error}"
                break
            else:
                reply.cancel()
                return ""
        else:
            text = "No he entendido la orden."
        try:
            if text and settings.volume:
                self.notify("speaking")
                speak(text, settings, self.changed)
        except ERRORS as error:
            return str(error)
        return ""
