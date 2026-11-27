"""Windows microphone capture and local System.Speech synthesis."""
import base64
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
from threading import Event
from time import monotonic

from voice_recognition import CHUNK_FRAMES, RATE

SAPI_SCRIPT = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voices = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled })
    if ($request.action -eq 'voices') {
        $items = @($voices | ForEach-Object {
            @{ name = $_.VoiceInfo.Name; culture = $_.VoiceInfo.Culture.Name }
        })
        Write-Output (ConvertTo-Json -InputObject $items -Compress)
    } elseif ($request.action -eq 'probe') {
        $memory = [System.IO.MemoryStream]::new()
        try {
            $speaker.SetOutputToWaveStream($memory)
            $speaker.Speak('JARVIS')
            $speaker.SetOutputToNull()
            Write-Output ($memory.ToArray().Length)
        } finally {
            $memory.Dispose()
        }
    } else {
        $selected = $voices | Where-Object { $_.VoiceInfo.Name -eq $request.voice } | Select-Object -First 1
        if (-not $selected) {
            $selected = $voices | Where-Object {
                $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es'
            } | Select-Object -First 1
        }
        if ($selected) { $speaker.SelectVoice($selected.VoiceInfo.Name) }
        $speaker.Volume = [int]$request.volume
        $speaker.Speak([string]$request.text)
    }
} finally {
    $speaker.Dispose()
}
"""


@dataclass(frozen=True)
class InputDevice:
    key: str
    label: str
    index: int
    wasapi: bool


@contextmanager
def portaudio():
    import sounddevice as sd

    try:
        yield sd
    except sd.PortAudioError as error:
        raise OSError(str(error)) from error


def input_devices(refresh=False):
    with portaudio() as sd:
        if refresh:
            # PortAudio takes a device snapshot at initialization. The voice
            # worker closes its stream before refreshing that snapshot.
            if sd._initialized:
                sd._terminate()
            sd._initialize()
        hosts = sd.query_hostapis()
        available = sd.query_devices()
    devices = []
    keys = Counter()
    for device in available:
        host = hosts[device["hostapi"]]["name"]
        if device["max_input_channels"] < 1 or host == "Windows WDM-KS":
            continue
        label = f'{device["name"]} ({host})'
        keys[label] += 1
        occurrence = keys[label]
        key = f"{label} #{occurrence}"
        devices.append(InputDevice(key, label if occurrence == 1 else key,
                                   device["index"], host == "Windows WASAPI"))
    return sorted(devices, key=lambda item: (not item.wasapi, item.label.casefold()))


class Microphone:
    def __init__(self, devices, selected):
        self.audio = Queue(maxsize=160)
        self.capturing = Event()
        self.lost = Event()
        self.capturing.set()

        def receive(indata, _frames, _time, _status):
            if self.capturing.is_set():
                try:
                    self.audio.put_nowait(bytes(indata))
                except Full:
                    self.lost.set()

        with portaudio() as sd:
            self.stream = self.open_stream(sd, devices, selected, receive)

    def open_stream(self, sd, devices, selected, callback):
        def open_input(index, wasapi):
            return sd.RawInputStream(
                device=index, samplerate=RATE, channels=1, dtype="int16",
                blocksize=CHUNK_FRAMES, latency="low", callback=callback,
                extra_settings=sd.WasapiSettings(auto_convert=True) if wasapi else None,
                finished_callback=self.lost.set,
            )

        if selected:
            device = next((device for device in devices if device.key == selected), None)
            if device is None:
                raise OSError("El micrófono seleccionado está desconectado.")
            return open_input(device.index, device.wasapi)
        default = next((api["default_input_device"] for api in sd.query_hostapis()
                        if api["name"] == "Windows WASAPI" and api["default_input_device"] >= 0), None)
        if default is not None:
            try:
                return open_input(default, True)
            except sd.PortAudioError:
                pass
        return open_input(None, False)

    def __enter__(self):
        with portaudio():
            try:
                self.stream.start()
            except Exception:
                self.stream.close()
                raise
        self.last_input = monotonic()
        return self

    def __exit__(self, *_error):
        with portaudio():
            self.stream.close()

    def read(self):
        with portaudio():
            active = self.stream.active
        if self.lost.is_set() or not active:
            raise OSError("Se interrumpió la entrada del micrófono.")
        try:
            pcm = self.audio.get(timeout=0.25)
        except Empty:
            if monotonic() - self.last_input > 2.0:
                raise OSError("El micrófono dejó de enviar audio.")
            return None
        self.last_input = monotonic()
        return pcm

    def pause(self):
        self.capturing.clear()

    def resume(self):
        while True:
            try:
                self.audio.get_nowait()
            except Empty:
                break
        self.last_input = monotonic()
        self.capturing.set()


def sapi(request, cancelled, timeout):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = base64.b64encode(SAPI_SCRIPT.encode("utf-16-le")).decode("ascii")
    with subprocess.Popen(
        [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW,
    ) as process:
        deadline = monotonic() + timeout
        payload = json.dumps(request)
        while not cancelled.is_set() and monotonic() < deadline:
            try:
                output, _errors = process.communicate(payload, timeout=0.25)
            except subprocess.TimeoutExpired:
                payload = None
            else:
                if process.returncode:
                    raise OSError("Windows no pudo usar la síntesis de voz instalada.")
                return output
        process.kill()
        process.communicate()
        if not cancelled.is_set():
            raise OSError("La síntesis de Windows tardó demasiado en responder.")
        return None


def installed_voices(cancelled):
    result = sapi({"action": "voices"}, cancelled, timeout=8)
    if result is None:
        return []
    voices = json.loads(result)
    return sorted(((item["name"], item["culture"]) for item in voices),
                  key=lambda item: (not item[1].lower().startswith("es"), item[0].casefold()))


def speak(text, settings, cancelled):
    if settings.volume == 0 or cancelled.is_set():
        return
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return
    line, *other = lines
    if other or len(line) > 210:
        line = "La respuesta completa está en el historial de JARVIS."
    sapi({"action": "speak", "text": line, "voice": settings.voice, "volume": settings.volume},
         cancelled, timeout=20)



def test_synthesis():
    result = sapi({"action": "probe"}, Event(), timeout=12)
    return int(result.strip())
