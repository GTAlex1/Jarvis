"""Run the voice loop independently of the Tk event loop and command worker."""
from concurrent.futures import TimeoutError
from queue import Empty, SimpleQueue
from threading import Event, Lock, Thread
from time import monotonic

from preferences import VoiceSettings
from audio_input import CaptureError, DefaultInputChanged, capture_input, input_devices
from voice_audio import installed_voices, speak
from voice_diagnostics import LOG, configure as configure_log
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
TEST_SECONDS = 5


class RecognitionError(OSError):
    pass


class VoiceService:
    def __init__(self, submit, on_state, on_catalog, on_test=None):
        self.submit = submit
        self.on_state = on_state
        self.on_catalog = on_catalog
        self.on_test = on_test
        self.meter = (0, "")
        self.test_lock = Lock()
        self.test_request = None
        self.testing = False
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

    def test_microphone(self, selection):
        with self.test_lock:
            self.test_request = selection
            self.changed.set()
        self.start()

    def cancel_test(self):
        with self.test_lock:
            if self.test_request is not None or self.testing:
                self.test_request = None
                self.changed.set()

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
        devices, voices, errors = None, [], []
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
        configure_log()
        try:
            self.run_loop()
        finally:
            self.model = None
            self.meter = (0, "")

    def run_loop(self):
        while not self.stopped.is_set():
            with self.test_lock:
                self.changed.clear()
                selection, self.test_request = self.test_request, None
                self.testing = selection is not None
            if self.stopped.is_set():
                break
            settings, microphone = self.config
            self.list_options()
            if selection is not None:
                try:
                    self.run_test(selection, microphone)
                finally:
                    with self.test_lock:
                        self.testing = False
                    self.meter = (0, "")
                    if self.changed.is_set() and self.on_test is not None and not self.stopped.is_set():
                        self.on_test("Prueba cancelada.")
                continue
            if not settings.enabled or not microphone:
                self.model = None
                self.notify("disabled" if microphone else "muted")
                self.changed.wait()
                continue
            if self.changed.is_set():
                continue
            try:
                self.notify("starting")
                self.run_capture(settings)
            except DefaultInputChanged as error:
                LOG.info("captura: %s", error)
            except ERRORS as error:
                self.model = None
                stage = "reconocimiento" if isinstance(error, RecognitionError) else "captura"
                LOG.error("%s: %s", stage, error)
                detail = ("Instala las dependencias de voz indicadas en el README."
                          if isinstance(error, ImportError) else str(error))
                self.notify("unavailable", detail)
                self.changed.wait(RETRY_SECONDS)

    def run_capture(self, settings):
        devices = input_devices(refresh=True)
        try:
            detector = WakeDetector(settings.sensitivity)
        except ERRORS as error:
            raise RecognitionError(f"No se pudo iniciar la detección de «Jarvis»: {error}") from error
        rejected = set()
        while not self.changed.is_set():
            capture = None
            try:
                with capture_input(devices, settings.device, self.changed, rejected) as capture:
                    if capture is not None:
                        self.listen(capture, detector, settings)
                    return
            except DefaultInputChanged:
                raise
            except CaptureError as error:
                if capture is None:
                    raise
                LOG.warning("captura interrumpida %s: %s", capture.label, error)
                rejected.add(capture.route.index)
                detector.reset()
            finally:
                self.meter = (0, "")

    def run_test(self, selection, microphone):
        if not microphone:
            self.on_test("Activa «Micrófono» en la bandeja para probar la entrada.")
            return
        try:
            devices = input_devices(refresh=True)
            with capture_input(devices, selection, self.changed) as capture:
                if capture is None:
                    return
                deadline = monotonic() + TEST_SECONDS
                while not self.changed.is_set() and monotonic() < deadline:
                    capture.read()
                    self.meter = (capture.level, capture.label)
                if not self.changed.is_set():
                    if capture.peak >= 33:  # about -60 dBFS
                        message = f"Señal recibida · {capture.label}"
                        LOG.info("captura prueba con señal %s, pico RMS %s", capture.label, capture.peak)
                    else:
                        message = f"Señal ausente o muy baja · {capture.label}"
                        LOG.warning("captura prueba sin señal útil %s, pico RMS %s", capture.label, capture.peak)
                    self.on_test(message)
        except ERRORS as error:
            LOG.error("captura prueba: %s", error)
            if not self.changed.is_set():
                self.on_test(f"Falló la prueba del micrófono: {error}")

    def listen(self, capture, detector, settings):
        exchange = Conversation(detector, self.recognize, self.notify)
        self.notify("waiting")
        while not self.changed.is_set():
            pcm = capture.read()
            self.meter = (capture.level, capture.label)
            now = monotonic()
            if pcm is None:
                continue
            if exchange.active is None and now - self.model_used > MODEL_IDLE_SECONDS:
                self.model = None
            was_listening = exchange.active is not None
            try:
                transcript = exchange.feed(pcm, now)
            except ERRORS as error:
                raise RecognitionError(f"Falló el reconocimiento de voz: {error}") from error
            if was_listening and exchange.active is None and transcript is None:
                LOG.info("reconocimiento: activación sin orden antes del tiempo de espera")
            if transcript is None or self.changed.is_set():
                continue
            self.notify("processing")
            capture.pause()
            self.meter = (0, capture.label)
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
            LOG.info("reconocimiento: orden descartada por baja confianza (%.2f)", transcript.confidence)
            text = "No he entendido la orden."
        try:
            if text and settings.volume:
                self.notify("speaking")
                speak(text, settings, self.changed)
        except ERRORS as error:
            return str(error)
        return ""
