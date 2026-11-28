"""Reproducible synthetic end-to-end benchmark; alternate models are optional."""
import argparse
import base64
import json
from pathlib import Path
import re
import sys
from statistics import median
from time import perf_counter, process_time
import zlib

FIXTURES = Path(__file__).resolve().parent / "tests" / "voice"
CASES = {
    "help": ("help",),
    "calc": ("open", "calculadora"),
    "quick": ("open", "calculadora"),
    "latin-help": ("help",),
    "separated": ("open", "spotify"),
    "power": ("system", "restart"),
    "restart": ("system", "restart"),
    "negcalc": None,
    "prefix": None,
    "other": None,
}


def pcm(name):
    if name == "separated":
        order = zlib.decompress(base64.b64decode((FIXTURES / "open-spotify.txt").read_bytes()))
        return pcm("wake") + b"\x00" * 16000 + order
    data = (FIXTURES / f"overhaul-{name}.txt").read_bytes()
    return zlib.decompress(base64.b64decode(data))


def benchmark(source, whisper_path):
    sys.path.insert(0, str(Path(source).resolve()))
    from command_language import normalize_order
    from commands import parse

    if whisper_path:
        import numpy as np
        from faster_whisper import WhisperModel

        model = WhisperModel(whisper_path, device="cpu", compute_type="int8", cpu_threads=2)

        def command(audio):
            wave = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768
            segments, _ = model.transcribe(wave, language="es", beam_size=1, condition_on_previous_text=False)
            text = " ".join(segment.text for segment in segments).strip()
            return (parse(normalize_order(text)) if re.match(r"(?i)^jarvis\b[, ]+", text) else None,
                    bool(re.match(r"(?i)^jarvis\b", text)))

    else:
        import voice_recognition as voice

        model = voice.spanish_model()

        def command(audio):
            if hasattr(voice, "corroborate_wake"):
                wake = voice.WakeDetector(3, corroborate=lambda data, level: voice.corroborate_wake(model, data, level))
                recover = {"recover": lambda data: voice.safe_redecode(model, data)}
            else:
                wake, recover = voice.WakeDetector(3), {}
            states = []
            conversation = voice.Conversation(wake, lambda: voice.SpanishRecognizer(model), states.append, **recover)
            stream = bytes(10000) + audio + bytes(96000)
            step = voice.CHUNK_FRAMES * voice.SAMPLE_BYTES
            for offset in range(0, len(stream), step):
                result = conversation.feed(stream[offset:offset + step], offset / (voice.RATE * voice.SAMPLE_BYTES))
                if result and result.understood:
                    return parse(normalize_order(result.text)), "listening" in states
            return None, "listening" in states

    idle_cpu = None
    if not whisper_path:
        take = voice.WakeDetector(3)
        frame = bytes(voice.CHUNK_FRAMES * voice.SAMPLE_BYTES)
        begin = process_time()
        for _ in range(1200):
            take.feed(frame)
        idle_cpu = round((process_time() - begin) * 1000)
        del take

    timings, results = [], {}
    start_cpu = process_time()
    for name, expected in CASES.items():
        start = perf_counter()
        intent, activated = command(pcm(name))
        timings.append(perf_counter() - start)
        results[name] = {"intent": intent, "expected": expected, "activated": activated, "correct": intent == expected}
    cpu = process_time() - start_cpu
    try:
        import resource
        peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1) if sys.platform == "linux" else None
    except ImportError:
        peak = None
    return {"cases": results, "correct": sum(item["correct"] for item in results.values()),
            "elapsed_ms": round(sum(timings) * 1000), "median_wall_ms": round(median(timings) * 1000),
            "cpu_ms": round(cpu * 1000), "peak_rss_mib": peak, "idle_cpu_ms_per_60s": idle_cpu}


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=Path(__file__).resolve().parent)
    parser.add_argument("--whisper-path", help="Local CTranslate2 Whisper model folder")
    options = parser.parse_args()
    print(json.dumps(benchmark(options.source, options.whisper_path), ensure_ascii=False))


if __name__ == "__main__":
    cli()
