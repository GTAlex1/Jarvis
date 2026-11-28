"""Render a local test report from synthetic audio without executing commands."""
import base64
import json
from pathlib import Path
from threading import Event
import zlib

from commands import parse
from command_language import normalize_order
from audio_input import AudioFormat, PcmConverter, input_devices
from voice_audio import installed_voices, test_synthesis
from speech_cancel import SpeechCancellation
from speakers import Profile
from biometric_audio import Reason, extract, verify
from voice_recognition import (
    CHUNK_FRAMES, RATE, SAMPLE_BYTES, Conversation, RecognitionProbe, SpanishRecognizer,
    WakeDetector, local_speaker_model, spanish_model, corroborate_wake, safe_redecode,
)


def fixture(folder, name):
    return zlib.decompress(base64.b64decode((folder / (name + ".txt")).read_bytes()))


def test_audio(folder):
    wake = fixture(folder, "wake-en")
    command = fixture(folder, "open-spotify")
    silence = bytes(RATE * SAMPLE_BYTES)
    model = spanish_model()
    cases = {
        "misma_frase": (wake[:-4800] + command, ["listening"], ("open", "spotify")),
        "pausa": (wake + silence[:len(silence) // 2] + command, ["listening"], ("open", "spotify")),
        "sin_activación": (command, [], None),
        "tiempo_agotado": (wake + silence * 7 + command, ["listening", "waiting"], None),
    }
    report = {}
    for name, (sample, expected_states, expected_order) in cases.items():
        states = []
        conversation = Conversation(WakeDetector(3), lambda: SpanishRecognizer(model), states.append)
        pcm = silence[:10000] + sample + silence * 3
        step = CHUNK_FRAMES * SAMPLE_BYTES
        order = None
        for start in range(0, len(pcm), step):
            transcript = conversation.feed(pcm[start:start + step], start / len(silence))
            if transcript and transcript.understood:
                order = parse(transcript.text)
                break
        if states != expected_states or order != expected_order:
            raise AssertionError(f"{name}: estados {states}, orden {order}")
        report[name] = "correcto"
    spanish_activation(model, folder)
    report["activación_española_y_negación"] = "correcto"
    high_rate_command(model, command)
    report["reconocimiento_192khz"] = "correcto"
    dialogue_audio(model, command, fixture(folder, "stop"), silence)
    report["continuación_e_interrupción"] = "correcto"
    verify_synthetic_speakers(model, command, fixture(folder, "stop"), wake)
    report["verificación_local_de_hablante"] = "correcto"
    return report


def spanish_activation(model, folder):
    cases = (
        ("overhaul-help", ("help",), True),
        ("overhaul-calc", ("open", "calculadora"), True),
        ("overhaul-negcalc", None, True),
        ("overhaul-prefix", None, False),
    )
    for name, expected, activation in cases:
        states = []
        wake = WakeDetector(3, corroborate=lambda data, level: corroborate_wake(model, data, level))
        session = Conversation(wake, lambda: SpanishRecognizer(model), states.append,
                               lambda data: safe_redecode(model, data))
        data = bytes(10000) + fixture(folder, name) + bytes(3 * RATE * SAMPLE_BYTES)
        step = CHUNK_FRAMES * SAMPLE_BYTES
        actual = None
        for offset in range(0, len(data), step):
            item = session.feed(data[offset:offset + step], offset / (RATE * SAMPLE_BYTES))
            if item and item.understood:
                actual = parse(normalize_order(item.text))
                break
        if actual != expected or ("listening" in states) != activation:
            raise AssertionError(f"{name}: estado {states}, intención {actual}")


def verify_synthetic_speakers(model, command, same, different):
    speaker_model = local_speaker_model()
    def read(audio):
        return extract(model, speaker_model, audio)

    enrolled = read(command).sample
    if enrolled is None:
        raise AssertionError("El modelo local no produjo una firma de voz.")
    profile = Profile("synthetic", "eSpeak", (enrolled.vector,) * 3)
    if verify(read, same, b"", (profile,), 0.72)[0] != Reason.ACCEPTED:
        raise AssertionError("No coincidieron frases sintéticas de la misma voz.")
    if verify(read, different, b"", (profile,), 0.72)[0] != Reason.UNAUTHORIZED:
        raise AssertionError("Una voz sintética distinta superó el umbral.")
    wake, short = same[:28400], same[28400:]
    if verify(read, short, wake, (profile,), 0.72)[0] != Reason.ACCEPTED:
        raise AssertionError("La frase sintética corta y continua no se verificó.")
    if verify(read, bytes(RATE) + short, wake, (profile,), 0.72)[0] != Reason.SHORT:
        raise AssertionError("Una orden breve tras una pausa se verificó con audio previo.")


def dialogue_audio(model, command, stop, silence):
    frame_bytes = CHUNK_FRAMES * SAMPLE_BYTES
    audio = silence[:10000] + command + silence * 2
    exchange = Conversation(WakeDetector(3), lambda: SpanishRecognizer(model), lambda _: None)
    exchange.listen_for_reply(0, 5)
    for start in range(0, len(audio), frame_bytes):
        transcript = exchange.feed(audio[start:start + frame_bytes], start / len(silence))
        if transcript and transcript.understood and parse(transcript.text) == ("open", "spotify"):
            break
    else:
        raise AssertionError("No se reconoció la orden de seguimiento sin activación.")

    class RecordedCapture:
        def __init__(self, pcm):
            self.frames = iter(pcm[start:start + frame_bytes] for start in range(0, len(pcm), frame_bytes))

        def read(self, timeout=0):
            return next(self.frames, None)

    for utterance, expected in ((command, False), (stop, True)):
        audio = silence[:10000] + utterance + silence * 2
        token = SpeechCancellation(Event(), Event(), RecordedCapture(audio), model)
        did_stop = any(token.is_set() for _ in range(len(audio) // frame_bytes + 1))
        if did_stop != expected or token.error:
            raise AssertionError(f"Resultado inesperado del reconocimiento de interrupción: {did_stop}.")


def high_rate_command(model, command):
    import audioop
    import numpy as np

    source = np.frombuffer(command, dtype="<i2")
    source = np.pad(source, (RATE // 5, RATE))
    audio = np.repeat(source, 12).astype(np.float32)
    frequencies = np.arange(len(audio), dtype=np.float64)
    audio += 9000 * np.sin(2 * np.pi * 31000 * frequencies / 192000)
    pcm = audio.clip(-32768, 32767).astype("<i2").tobytes()
    converter = PcmConverter(AudioFormat(192000, 1))
    detector = RecognitionProbe(SpanishRecognizer(model))
    chunk = 192000 * SAMPLE_BYTES // 20
    have_partial = False
    for start in range(0, len(pcm), chunk):
        sample = converter.convert(pcm[start:start + chunk])
        reading = detector.feed(sample, audioop.rms(sample, 2))
        have_partial |= bool(reading.text)
    final = detector.finish()
    if not (final.signal and final.voice and final.recognized and have_partial and
            parse(final.text) == ("open", "spotify")):
        raise AssertionError(f"192 kHz: {final.status()} · {final.text!r}")


def report(fixture_path, output_path):
    try:
        results = test_audio(Path(fixture_path))
        pcm = PcmConverter(AudioFormat(48000, 2)).convert(b"\x00\x04" * 4800)
        if len(pcm) != 1600 or not any(pcm):
            raise AssertionError("La conversión local a mono y 16 kHz no devolvió señal.")
        results["conversión_pcm"] = "correcto"
        devices = input_devices()
        voices = installed_voices(Event())
        if not voices or test_synthesis() <= 44:
            raise AssertionError("La síntesis de Windows no generó una señal.")
        results.update(dispositivos_detectados=len(devices.devices), voces_instaladas=len(voices),
                       síntesis_en_memoria="correcto")
        code = 0
    except Exception as error:
        results = {"error": f"{type(error).__name__}: {error}"}
        code = 1
    Path(output_path).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return code
