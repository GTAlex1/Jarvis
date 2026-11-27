"""Run the voice loop independently of the Tk event loop and command worker."""
from concurrent.futures import TimeoutError
from queue import Empty, SimpleQueue
from threading import Event, Lock, Thread
from time import monotonic

from preferences import VoiceSettings
from commands import parse
from dialogue import Dialogue, Turn, split_speech
from speech_cancel import SpeechCancellation
from audio_input import CaptureError, DefaultInputChanged, capture_input, input_devices, reject_recognition
from voice_audio import installed_voices, speak
from voice_diagnostics import LOG, configure as configure_log
from voice_recognition import Conversation, RecognitionProbe, SpanishRecognizer, WakeDetector, spanish_model

STATE_LABELS = {
    "disabled": "Escucha permanente desactivada",
    "muted": "Micrófono desactivado",
    "starting": "Preparando micrófono",
    "waiting": "En espera · di «Jarvis»",
    "listening": "Escuchando la orden",
    "followup": "Escuchando tu respuesta",
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
RECOGNITION_FAILURES = 2


class RecognitionError(OSError):
    pass


class RecognitionRouteError(RecognitionError):
    pass


class VoiceService:
    def __init__(self, submit, on_state, on_catalog, on_test=None):
        self.submit = submit
        self.on_state = on_state
        self.on_catalog = on_catalog
        self.on_test = on_test
        self.meter = (0, "")
        self.test_progress = None
        self.preferred_routes = {}
        self.test_lock = Lock()
        self.test_request = None
        self.testing = False
        self.changed = Event()
        self.stopped = Event()
        self.speech_stop = Event()
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

    def test_microphone(self, selection, interface=""):
        with self.test_lock:
            self.test_progress = None
            self.test_request = (selection, interface)
            self.changed.set()
        self.start()

    def cancel_test(self):
        with self.test_lock:
            if self.test_request is not None or self.testing:
                self.test_request = None
                self.changed.set()

    def stop_speech(self):
        self.speech_stop.set()

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
                request, self.test_request = self.test_request, None
                self.testing = request is not None
            if self.stopped.is_set():
                break
            settings, microphone = self.config
            self.list_options()
            if request is not None:
                try:
                    self.run_test(*request, microphone)
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
        selection, interface = devices.migrate(settings.device, settings.interface)
        preferred = self.preferred_routes.get(selection, "")
        rejected = set()
        while not self.changed.is_set():
            capture = None
            try:
                with capture_input(devices, selection, self.changed, rejected, interface, preferred,
                                   recover_interface=True) as capture:
                    if capture is not None:
                        automatic = capture.automatic and (
                            capture.route.api == "Windows WASAPI" or
                            len({r.api for r in capture.available_routes}) > 1
                        )
                        self.listen(capture, detector, settings, automatic=automatic)
                    return
            except DefaultInputChanged:
                self.preferred_routes.pop("", None)
                raise
            except (CaptureError, RecognitionRouteError) as error:
                if capture is None:
                    raise
                stage = "reconocimiento" if isinstance(error, RecognitionRouteError) else "captura"
                LOG.warning("%s: probando otra ruta tras %s: %s", stage, capture.label, error)
                if isinstance(error, RecognitionRouteError):
                    reject_recognition(capture, rejected, whole_interface=True)
                else:
                    rejected.add(capture.route.index)
                if preferred == capture.route.legacy_key:
                    preferred = ""
                    self.preferred_routes.pop(selection, None)
                detector.reset()
            finally:
                self.meter = (0, "")

    def preview(self, capture):
        try:
            probe = RecognitionProbe(self.recognize())
            deadline = monotonic() + TEST_SECONDS
            while not self.changed.is_set() and monotonic() < deadline:
                pcm = capture.read()
                self.meter = (capture.level, capture.label)
                if pcm is not None:
                    self.test_progress = probe.feed(pcm, capture.peak)
            if not self.changed.is_set():
                return probe.finish()
        except CaptureError:
            raise
        except ERRORS as error:
            raise RecognitionError(str(error)) from error
        return None

    def run_test(self, selection, interface, microphone):
        if not microphone:
            self.on_test("Activa «Micrófono» en la bandeja para probar la entrada.")
            return
        best, label = None, ""
        rejected = set()
        try:
            devices = input_devices(refresh=True)
            selection, interface = devices.migrate(selection, interface)
            while not self.changed.is_set():
                capture = None
                try:
                    with capture_input(devices, selection, self.changed, rejected, interface) as capture:
                        if capture is None:
                            return
                        self.test_progress = None
                        reading = self.preview(capture)
                        if reading is None:
                            return
                        LOG.info("prueba de voz %s: %s", capture.label, reading.status())
                        score = (reading.recognized, reading.voice, reading.signal)
                        if best is None or score > (best.recognized, best.voice, best.signal):
                            best, label = reading, capture.label
                        if reading.recognized and reading.voice:
                            if not interface:
                                self.preferred_routes[selection] = capture.route.legacy_key
                            break
                        reject_recognition(capture, rejected)
                except CaptureError as error:
                    LOG.warning("captura prueba: %s", error)
                    if capture is not None:
                        rejected.add(capture.route.index)
                        continue
                    if best is None:
                        raise
                    break
            if best is not None and not self.changed.is_set():
                self.test_progress = best
                self.on_test(f"{best.status()} · {label}")
        except ERRORS as error:
            stage = "reconocimiento" if isinstance(error, RecognitionError) else "captura"
            LOG.error("%s prueba: %s", stage, error)
            if not self.changed.is_set():
                self.on_test(f"Falló la prueba de {stage}: {error}")

    def listen(self, capture, detector, settings, automatic=False):
        failures = 0
        dialogue = Dialogue(settings.speech_detail, settings.conversational)
        exchange = Conversation(detector, self.recognize, self.notify)
        self.notify("waiting", capture.notice)
        while not self.changed.is_set():
            if self.speech_stop.is_set():
                self.speech_stop.clear()
                dialogue.clear()
                exchange.reset()
            pcm = capture.read()
            self.meter = (capture.level, capture.label)
            now = monotonic()
            dialogue.expire(now)
            if pcm is None:
                continue
            if exchange.active is None and now - self.model_used > MODEL_IDLE_SECONDS:
                self.model = None
            was_listening = exchange.active is not None
            following = exchange.following
            try:
                transcript = exchange.feed(pcm, now)
            except ERRORS as error:
                raise RecognitionError(f"Falló el reconocimiento de voz: {error}") from error
            if was_listening and exchange.active is None and transcript is None:
                if following:
                    dialogue.abandon_question()
                else:
                    LOG.info("reconocimiento: activación sin orden antes del tiempo de espera")
                    failures += 1
                    self.check_route(automatic, failures)
            if transcript is None or self.changed.is_set():
                continue
            if following and transcript.confidence < 0.73:
                # Ignore uncertain background speech without reopening the wake gate.
                continue
            capture.pause()
            self.meter = (0, capture.label)
            self.notify("processing")
            turn = self.interpret(transcript, dialogue, settings, now)
            if following and not turn.accepted:
                capture.resume()
                self.notify("followup")
                continue
            if not following:
                failures = 0 if turn.accepted else failures + 1
            warning, interrupted = self.play(turn.speech, settings, capture)
            if self.changed.wait(PLAYBACK_GUARD_SECONDS):
                return
            capture.resume()
            exchange.reset()
            self.check_route(automatic, failures)
            if interrupted:
                self.speech_stop.clear()
                dialogue.clear()
            elif settings.conversational and settings.volume and turn.speech and turn.accepted and not (turn.end or warning):
                now = monotonic()
                dialogue.keep(now, settings.context_seconds)
                exchange.listen_for_reply(now, min(settings.reply_seconds, settings.context_seconds))
            if warning:
                LOG.warning("síntesis: %s", warning)

    @staticmethod
    def check_route(automatic, failures):
        if automatic and failures >= RECOGNITION_FAILURES:
            raise RecognitionRouteError("Dos activaciones consecutivas sin una orden reconocida.")

    def interpret(self, transcript, dialogue, settings, now):
        if not transcript.understood:
            LOG.info("reconocimiento: orden descartada por baja confianza (%.2f)", transcript.confidence)
            return Turn(speech="No he entendido la orden.", accepted=False)
        if settings.conversational:
            turn = dialogue.turn(transcript.text, now)
        elif parse(transcript.text):
            turn = Turn(command=transcript.text)
        else:
            return Turn(speech="No he entendido la orden. Puedes decir ayuda.", accepted=False)
        if turn.command is None:
            return turn
        self.notify("executing")
        reply = self.submit(turn.command)
        while not self.changed.is_set() and not self.speech_stop.is_set():
            try:
                result = reply.result(timeout=0.2)
            except TimeoutError:
                continue
            except Exception as error:
                result = f"No pude completar la orden: {error}"
            return dialogue.answer(turn.command, result)
        reply.cancel()
        return Turn(end=True)

    def play(self, text, settings, capture=None):
        if not text or not settings.volume:
            return "", self.speech_stop.is_set()
        self.notify("speaking")
        try:
            for part in split_speech(text):
                # During playback only the explicit stop grammar has access
                # to microphone frames. The command recognizer stays out.
                model = self.model if capture is not None and "jarvis" not in part.casefold() else None
                try:
                    token = SpeechCancellation(self.changed, self.speech_stop, capture, model)
                except ERRORS as error:
                    LOG.warning("reconocimiento: no se pudo iniciar la interrupción por voz: %s", error)
                    model = None
                    token = SpeechCancellation(self.changed, self.speech_stop, capture)
                if self.changed.is_set() or self.speech_stop.is_set():
                    break
                if model:
                    capture.resume()
                try:
                    speak(part, settings, token)
                finally:
                    if model:
                        capture.pause()
                if token.error:
                    raise token.error
        except CaptureError:
            raise
        except ERRORS as error:
            return str(error), self.speech_stop.is_set()
        return "", self.speech_stop.is_set()
