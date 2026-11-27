"""Windows microphone capture and local System.Speech synthesis."""
import base64
import json
import os
from pathlib import Path
import subprocess
from threading import Event
from time import monotonic

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
