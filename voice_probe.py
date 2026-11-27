"""Render a local test report from synthetic audio without executing commands."""
import base64
import json
from pathlib import Path
from threading import Event
import zlib

from commands import parse
from audio_input import AudioFormat, PcmConverter, input_devices
from voice_audio import installed_voices, test_synthesis
from voice_recognition import (
    CHUNK_FRAMES, RATE, SAMPLE_BYTES, Conversation, RecognitionProbe, SpanishRecognizer, WakeDetector, spanish_model,
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
    return report


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
