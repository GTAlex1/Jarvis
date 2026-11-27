"""Run the voice loop independently of the Tk event loop and command worker."""
from concurrent.futures import TimeoutError
from queue import Empty, SimpleQueue
from threading import Event, Lock, Thread
from time import monotonic

from preferences import VoiceSettings
from commands import WAKE_WORD, clean, parse
from command_language import normalize_order
from dialogue import STOP, Dialogue, Turn, split_speech
from speech_cancel import SpeechCancellation
from audio_input import CaptureError, DefaultInputChanged, capture_input, input_devices, reject_recognition
from voice_audio import installed_voices, speak
from voice_diagnostics import LOG, configure as configure_log
from biometric_audio import MESSAGES, Reason, extract, verify
from speakers import ENROLLMENT_FRAMES
from voice_authorization import UNVERIFIED
from voice_recognition import (Conversation, RecognitionProbe, SpanishRecognizer, WakeDetector,
                               local_speaker_model, spanish_model)

STATE_LABELS = {
    "disabled": "Escucha permanente desactivada",
    "muted": "Micrófono desactivado",
    "starting": "Preparando micrófono",
    "waiting": f"En espera · di «{WAKE_WORD}»",
    "profiles": "Registra un perfil de voz para escuchar",
    "voice_rejected": "Voz sin autorización",
    "voice_short": "Muestra de voz insuficiente",
    "voice_quality": "Audio insuficiente para verificar",
    "voice_error": "Error de verificación de voz",
    "profile_damaged": "Perfil de voz incompatible o dañado",
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
    def __init__(self, submit, on_state, on_catalog, on_test=None, on_cancel=None):
        self.submit = submit
        self.on_state = on_state
        self.on_catalog = on_catalog
        self.on_test = on_test
        self.on_cancel = on_cancel
        self.meter = (0, "")
        self.test_progress = None
        self.preferred_routes = {}
        self.test_lock = Lock()
        self.test_request = None
        self.testing = False
        self.profiles = ()
        self.profile_error = False
        self.biometrics = True
        self.last_biometrics = {}
        self.current_route = None
        self.speaker_model = None
        self.enrollment_request = None
        self.enrolling = False
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

    def set_profiles(self, profiles, error=False):
        self.profiles = tuple(profiles)
        self.profile_error = bool(error)
        self.changed.set()

    def set_security(self, biometrics):
        self.biometrics = biometrics
        self.changed.set()

    def record_speaker(self, on_progress, on_done, minimum=ENROLLMENT_FRAMES):
        with self.test_lock:
            self.enrollment_request = (on_progress, on_done, minimum)
            self.changed.set()
        self.start()

    def cancel_enrollment(self):
        with self.test_lock:
            if self.enrollment_request is not None or self.enrolling:
                self.enrollment_request = None
                self.changed.set()

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
            self.model = self.speaker_model = None
            self.meter = (0, "")

    def run_loop(self):
        while not self.stopped.is_set():
            with self.test_lock:
                self.changed.clear()
                request, self.test_request = self.test_request, None
                self.testing = request is not None
                enrollment, self.enrollment_request = self.enrollment_request, None
                self.enrolling = enrollment is not None
            if self.stopped.is_set():
                break
            settings, microphone = self.config
            self.list_options()
            if enrollment is not None:
                try:
                    self.run_enrollment(settings, microphone, *enrollment)
                finally:
                    with self.test_lock:
                        self.enrolling = False
                    self.meter = (0, "")
                if request is not None and self.on_test is not None:
                    self.on_test("Prueba cancelada durante el registro de voz.")
                continue
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
                self.model = self.speaker_model = None
                self.notify("disabled" if microphone else "muted")
                self.changed.wait()
                continue
            if self.biometrics and (self.profile_error or not self.profiles):
                self.model = self.speaker_model = None
                self.notify("profile_damaged" if self.profile_error else "profiles",
                            MESSAGES[Reason.DAMAGED if self.profile_error else Reason.MISSING])
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

    def sample(self, pcm, minimum=None):
        if self.model is None:
            self.model = spanish_model()
        if self.speaker_model is None:
            self.speaker_model = local_speaker_model()
        self.model_used = monotonic()
        reading = (extract(self.model, self.speaker_model, pcm) if minimum is None
                   else extract(self.model, self.speaker_model, pcm, minimum))
        self.last_biometrics = {
            "calidad": reading.reason.value if reading.reason else "adecuada",
            "voz_ms": reading.voiced_ms, "pico_porcentaje": reading.peak_percent,
            "fotogramas": reading.sample.frames if reading.sample else 0,
        }
        return reading

    def set_capture_diagnostics(self, capture):
        self.current_route = {
            "interfaz": capture.route.api, "frecuencia": capture.format.rate,
            "canales": capture.format.channels, "formato": capture.format.dtype,
        }

    def run_enrollment(self, settings, microphone, progress, done, minimum):
        if not microphone:
            done(None, "Activa el micrófono en la bandeja antes de grabar.")
            return
        try:
            devices = input_devices(refresh=True)
            selection, interface = devices.migrate(settings.device, settings.interface)
            preferred = self.preferred_routes.get(selection, "")
            with capture_input(devices, selection, self.changed, interface=interface,
                               preferred=preferred, recover_interface=True) as capture:
                if capture is None:
                    done(None, "Grabación cancelada.")
                    return
                self.set_capture_diagnostics(capture)
                progress("Habla ahora. Usa una frase de varios segundos.")
                audio = bytearray()
                deadline = monotonic() + 5
                while not self.changed.is_set() and monotonic() < deadline:
                    pcm = capture.read()
                    self.meter = (capture.level, capture.label)
                    if pcm:
                        audio.extend(pcm)
                if self.changed.is_set():
                    done(None, "Grabación cancelada.")
                    return
                if not interface:
                    self.preferred_routes[selection] = capture.route.legacy_key
            reading = self.sample(bytes(audio), minimum)
            self.last_biometrics["uso"] = "registro_o_prueba"
            done(reading.sample, reading.message())
        except ERRORS as error:
            self.last_biometrics = {"resultado": Reason.ERROR.value, "uso": "registro_o_prueba"}
            LOG.warning("biometría: error de registro (%s)", type(error).__name__)
            done(None, "No se pudo grabar o verificar la muestra. Comprueba el micrófono y su interfaz.")

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
                        self.set_capture_diagnostics(capture)
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
        owner = None
        threshold = settings.speaker_threshold / 100
        self.notify("waiting", capture.notice)
        while not self.changed.is_set():
            if self.speech_stop.is_set():
                self.speech_stop.clear()
                dialogue.clear()
                owner = None
                exchange.reset()
            pcm = capture.read()
            self.meter = (capture.level, capture.label)
            now = monotonic()
            dialogue.expire(now)
            if pcm is None:
                continue
            if exchange.active is None and now - self.model_used > MODEL_IDLE_SECONDS:
                self.model = self.speaker_model = None
            was_listening = exchange.active is not None
            following = exchange.following
            try:
                transcript = exchange.feed(pcm, now)
                if not was_listening and exchange.active is not None:
                    owner = None
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
            capture.pause()
            self.meter = (0, capture.label)
            text = clean(transcript.text)
            safe_stop = transcript.confidence >= 0.73 and (
                text in STOP or text in {"deten la operacion", "cancela la orden", "no confirmo la orden"} or
                (following and text in {"no", "no gracias", "no, gracias", "no cancela la orden"})
            )
            if following and transcript.confidence < 0.73 and not safe_stop:
                capture.resume()
                exchange.listen_for_reply(now, max(0, exchange.deadline - now))
                continue
            if safe_stop and self.on_cancel:
                self.on_cancel(None)  # Cancelling never grants permission.
                dialogue.clear()
                turn = Turn(speech="De acuerdo, cancelado.", end=True)
            elif self.biometrics:
                self.last_biometrics = {}
                reason, speaker = verify(self.sample, bytes(exchange.audio), exchange.activation,
                                         self.profiles, threshold, owner)
                self.last_biometrics.update(uso="orden", resultado=reason.value)
                LOG.info("biometría: %s", reason.value)
                if speaker is None:
                    if reason == Reason.UNAUTHORIZED:
                        dialogue.clear()
                        owner = None
                        self.notify("voice_rejected", MESSAGES[reason])
                        turn = Turn(end=True, accepted=False)
                    else:
                        state = ("voice_short" if reason == Reason.SHORT else
                                 "voice_error" if reason in {Reason.ERROR, Reason.MISSING} else "voice_quality")
                        self.notify(state, MESSAGES[reason])
                        prompt = MESSAGES[reason]
                        if reason == Reason.SHORT and dialogue.verbal:
                            prompt = "Necesito más voz. Di «Sí, confirma la orden», o di «cancela»."
                        elif reason == Reason.SHORT and text == "ayuda":
                            prompt = "Necesito más voz. Di «Dime cómo puedes ayudarme»."
                        turn = Turn(speech=prompt, followup=True)
                else:
                    owner = speaker
                    self.notify("processing")
                    turn = self.interpret(transcript, dialogue, settings, now, speaker)
            else:
                owner = UNVERIFIED
                self.notify("processing")
                turn = self.interpret(transcript, dialogue, settings, now, owner)
            if self.changed.is_set():
                return
            if following and not turn.accepted and not turn.end:
                capture.resume()
                exchange.listen_for_reply(now, max(0, exchange.deadline - now))
                continue
            if not following and not turn.end:
                failures = 0 if turn.accepted else failures + 1
            warning, interrupted = self.play(turn.speech, settings, capture, owner)
            if self.changed.wait(PLAYBACK_GUARD_SECONDS if turn.speech else 0):
                return
            capture.resume()
            if turn.speech or turn.accepted:
                exchange.reset()
            else:
                # Keep the specific rejection visible until a new activation.
                exchange.reset(notify=False)
            self.check_route(automatic, failures)
            if interrupted:
                self.speech_stop.clear()
                if self.on_cancel:
                    self.on_cancel(None)
                dialogue.clear()
                owner = None
            elif not turn.end and not warning and (turn.followup or (
                settings.conversational and settings.volume and turn.speech and turn.accepted
            )):
                now = monotonic()
                if not turn.followup or not dialogue.expires:
                    dialogue.keep(now, settings.context_seconds)
                exchange.listen_for_reply(now, min(settings.reply_seconds, settings.context_seconds))
            else:
                owner = None
            if warning:
                LOG.warning("síntesis: %s", warning)

    @staticmethod
    def check_route(automatic, failures):
        if automatic and failures >= RECOGNITION_FAILURES:
            raise RecognitionRouteError("Dos activaciones consecutivas sin una orden reconocida.")

    def interpret(self, transcript, dialogue, settings, now, speaker=None):
        if speaker is None:
            return Turn(end=True, accepted=False)
        if not transcript.understood or (dialogue.verbal and transcript.confidence < 0.73):
            LOG.info("reconocimiento: orden descartada por baja confianza (%.2f)", transcript.confidence)
            return Turn(speech="No he entendido la orden.", accepted=False)
        text = normalize_order(transcript.text)
        intent = parse(text)
        if intent and intent[0] not in {"apps", "windows", "screens", "help"} and transcript.confidence < 0.66:
            return Turn(speech="La orden no se oyó con claridad. Repítela, por favor.", accepted=False)
        if self.on_cancel and clean(text) in STOP:
            self.on_cancel(speaker)
        if settings.conversational or dialogue.verbal:
            turn = dialogue.turn(text, now)
        elif parse(text):
            turn = Turn(command=text)
        else:
            return Turn(speech="No he entendido la orden. Puedes decir ayuda.", accepted=False)
        if turn.command is None:
            return turn
        self.notify("executing")
        reply = self.submit(turn.command, speaker)
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

    def play(self, text, settings, capture=None, speaker=None):
        if not text or not settings.volume:
            return "", self.speech_stop.is_set()
        self.notify("speaking")
        try:
            for part in split_speech(text):
                # During playback only the explicit stop grammar has access
                # to microphone frames. The command recognizer stays out.
                model = self.model if capture is not None and WAKE_WORD.casefold() not in part.casefold() else None
                try:
                    # Stopping speech or a pending operation is always safe.
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
