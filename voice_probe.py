"""Render a local test report from synthetic audio without executing commands."""
import base64
import json
from pathlib import Path
from threading import Event
import zlib

from commands import parse
from voice_audio import input_devices, installed_voices, test_synthesis
from voice_recognition import CHUNK_FRAMES, RATE, SAMPLE_BYTES, Conversation, SpanishRecognizer, WakeDetector, spanish_model


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
    return report


def report(fixture_path, output_path):
    try:
        results = test_audio(Path(fixture_path))
        devices = input_devices()
        voices = installed_voices(Event())
        if not voices or test_synthesis() <= 44:
            raise AssertionError("La síntesis de Windows no generó una señal.")
        results.update(dispositivos_detectados=len(devices), voces_instaladas=len(voices),
                       síntesis_en_memoria="correcto")
        code = 0
    except Exception as error:
        results = {"error": f"{type(error).__name__}: {error}"}
        code = 1
    Path(output_path).write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return code
