"""Render a local test report from synthetic audio without executing commands."""
import base64
import json
from pathlib import Path
from threading import Event
import zlib

from commands import parse
from audio_input import AudioFormat, PcmConverter, input_devices
from voice_audio import installed_voices, test_synthesis
from speech_cancel import SpeechCancellation
from speakers import Profile, identify
from voice_recognition import (
    CHUNK_FRAMES, RATE, SAMPLE_BYTES, Conversation, RecognitionProbe, SpanishRecognizer, WakeDetector, local_speaker_model, spanish_model,
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
    high_rate_command(model, command)
    report["reconocimiento_192khz"] = "correcto"
    dialogue_audio(model, command, fixture(folder, "stop"), silence)
    report["continuación_e_interrupción"] = "correcto"
    verify_synthetic_speakers(model, command, fixture(folder, "stop"), wake)
    report["verificación_local_de_hablante"] = "correcto"
    return report


def verify_synthetic_speakers(model, command, same, different):
    speaker_model = local_speaker_model()
    samples = []
    for fixture in (command, same, different):
        decoder = SpanishRecognizer(model, speaker_model=speaker_model)
        audio = bytes(16000) + fixture + bytes(32000)
        transcripts = []
        step = CHUNK_FRAMES * SAMPLE_BYTES
        for start in range(0, len(audio), step):
            if result := decoder.feed(audio[start:start + step]):
                transcripts.append(result)
        if result := decoder.finish():
            transcripts.append(result)
        vectors = [result.speaker for result in transcripts if result.speaker]
        if not vectors:
            raise AssertionError("El modelo local no produjo una firma de voz.")
        samples.append(max(vectors, key=lambda sample: sample.frames))

    enrolled = Profile("synthetic", "eSpeak", (samples[0].vector,) * 3)
    if identify(samples[1], (enrolled,), 0.72) != enrolled.id:
        raise AssertionError("No coincidieron frases sintéticas de la misma voz.")
    if identify(samples[2], (enrolled,), 0.72) is not None:
        raise AssertionError("Una voz sintética distinta superó el umbral.")



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
