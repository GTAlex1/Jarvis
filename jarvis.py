import ctypes as c
from ctypes import wintypes as w
from pathlib import PureWindowsPath
import re
import subprocess
import sys
import unicodedata


def normalize(value):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value.lower())
        if not unicodedata.combining(ch)
    ).strip().rstrip(".!?")


MOVE = re.compile(
    r"(?:oye jarvis[, ]+)?(?:mueve|pon|coloca) "
    r"(?:(?:la )?(?:ventana|pestana)(?: de)? )?"
    r"(?:(?:el|la) )?(.+?) (?:a|en) (?:la )?(?:mitad )?(izquierda|derecha)"
    r"(?: (?:de|del) (?:la |el )?(?:pantalla|monitor) (\d+))?"
)
APP_NAMES = {
    "code": ("Visual Studio Code", "VSCode", "VS Code"),
    "chrome": ("Google Chrome", "Chrome"),
    "msedge": ("Microsoft Edge", "Edge"),
    "firefox": ("Firefox", "Mozilla Firefox"),
    "explorer": ("Explorador de archivos", "Explorador", "File Explorer"),
    "notepad": ("Bloc de notas", "Notepad"),
    "calc": ("Calculadora", "Calculator"),
    "calculatorapp": ("Calculadora", "Calculator"),
    "winword": ("Microsoft Word", "Word"),
    "excel": ("Microsoft Excel", "Excel"),
    "powerpnt": ("Microsoft PowerPoint", "PowerPoint"),
}


def parse_move(command):
    match = MOVE.fullmatch(normalize(command))
    if match:
        title, side, screen = match.groups()
        return title, side, int(screen) if screen else None


def app_label(executable):
    return APP_NAMES.get(normalize(executable), (executable,))[0]


def matching_windows(windows, query):
    exact = [
        window for window in windows
        if query == normalize(window[1])
        or query in {
            normalize(name)
            for name in (window[2], *APP_NAMES.get(normalize(window[2]), ()))
            if name
        }
    ]
    if exact:
        return exact
    return [window for window in windows if query in normalize(window[1])]


def half(bounds, side):
    x, y, right, bottom = bounds
    middle = x + (right - x) // 2
    if side == "izquierda":
        return x, y, middle - x, bottom - y
    return middle, y, right - middle, bottom - y


class MonitorInfo(c.Structure):
    _fields_ = [
        ("size", w.DWORD), ("monitor", w.RECT), ("work", w.RECT),
        ("flags", w.DWORD), ("device", w.WCHAR * 32)
    ]


class Desktop:
    def __init__(self):
        self.api = c.WinDLL("user32", use_last_error=True)
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.kernel.OpenProcess.restype = w.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD),
        ]
        self.kernel.QueryFullProcessImageNameW.restype = w.BOOL
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.kernel.CloseHandle.restype = w.BOOL
        self.window_callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        self.monitor_callback = c.WINFUNCTYPE(
            w.BOOL, w.HMONITOR, w.HDC, c.POINTER(w.RECT), w.LPARAM
        )
        signatures = {
            "SetProcessDpiAwarenessContext": ([w.HANDLE], w.BOOL),
            "EnumDisplayMonitors": ([w.HDC, c.POINTER(w.RECT), self.monitor_callback, w.LPARAM], w.BOOL),
            "GetMonitorInfoW": ([w.HMONITOR, c.POINTER(MonitorInfo)], w.BOOL),
            "EnumWindows": ([self.window_callback, w.LPARAM], w.BOOL),
            "GetWindowThreadProcessId": ([w.HWND, c.POINTER(w.DWORD)], w.DWORD),
            "IsWindowVisible": ([w.HWND], w.BOOL),
            "GetWindowTextLengthW": ([w.HWND], c.c_int),
            "GetWindowTextW": ([w.HWND, w.LPWSTR, c.c_int], c.c_int),
            "IsZoomed": ([w.HWND], w.BOOL),
            "IsIconic": ([w.HWND], w.BOOL),
            "ShowWindow": ([w.HWND, c.c_int], w.BOOL),
            "SetWindowPos": ([w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT], w.BOOL),
            "GetWindowRect": ([w.HWND, c.POINTER(w.RECT)], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes = args
            function.restype = result
        self.api.SetProcessDpiAwarenessContext(c.c_void_p(-4))

    def screens(self):
        screens = {}

        @self.monitor_callback
        def collect(handle, _dc, _rect, _data):
            info = MonitorInfo()
            info.size = c.sizeof(info)
            if self.api.GetMonitorInfoW(handle, c.byref(info)):
                number = re.search(r"DISPLAY(\d+)$", info.device, re.I)
                if number:
                    work = info.work
                    screens[int(number[1])] = (
                        (work.left, work.top, work.right, work.bottom), bool(info.flags & 1)
                    )
            return True

        if not self.api.EnumDisplayMonitors(None, None, collect, 0):
            raise c.WinError(c.get_last_error())
        return screens

    def executable(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid)
        if not process:
            return ""
        try:
            path = c.create_unicode_buffer(32768)
            size = w.DWORD(len(path))
            if self.kernel.QueryFullProcessImageNameW(process, 0, path, c.byref(size)):
                return PureWindowsPath(path.value).stem
            return ""
        finally:
            self.kernel.CloseHandle(process)

    def windows(self):
        windows = []
        executables = {}

        @self.window_callback
        def collect(handle, _data):
            if self.api.IsWindowVisible(handle):
                title = c.create_unicode_buffer(self.api.GetWindowTextLengthW(handle) + 1)
                if self.api.GetWindowTextW(handle, title, len(title)):
                    pid = w.DWORD()
                    self.api.GetWindowThreadProcessId(handle, c.byref(pid))
                    if pid.value not in executables:
                        executables[pid.value] = self.executable(pid.value)
                    windows.append((handle, title.value, executables[pid.value]))
            return True

        if not self.api.EnumWindows(collect, 0):
            raise c.WinError(c.get_last_error())
        return windows

    def move(self, title, side, screen):
        screens = self.screens()
        if screen is None:
            screen = next((number for number, (_, primary) in screens.items() if primary), None)
        if screen not in screens:
            return "No encontré esa pantalla. Escribe «pantallas» para ver las disponibles."

        matches = matching_windows(self.windows(), title)
        if not matches:
            return f"No encontré una ventana que coincida con «{title}»."
        if len(matches) > 1:
            names = "\n".join(f"  {name}" for _, name, _ in matches)
            return f"Encontré varias ventanas. Repite la orden con un título más específico:\n{names}"

        handle, name, _ = matches[0]
        if self.api.IsZoomed(handle) or self.api.IsIconic(handle):
            self.api.ShowWindow(handle, 9)  # SW_RESTORE
        target = half(screens[screen][0], side)
        flags = 0x0014  # SWP_NOZORDER | SWP_NOACTIVATE
        if not self.api.SetWindowPos(handle, None, *target, flags):
            raise c.WinError(c.get_last_error())

        actual = w.RECT()
        if not self.api.GetWindowRect(handle, c.byref(actual)):
            raise c.WinError(c.get_last_error())
        measured = (actual.left, actual.top, actual.right - actual.left, actual.bottom - actual.top)
        if measured != target:
            return f"Moví «{name}», pero la ventana quedó en {measured} y el área solicitada era {target}."
        return f"Moví «{name}» a la mitad {side} de la pantalla {screen}."


def listen():
    script = """
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Add-Type -AssemblyName System.Speech
    $recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
        Where-Object { $_.Culture.TwoLetterISOLanguageName -eq 'es' } |
        Select-Object -First 1
    if (-not $recognizer) { exit 2 }
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($recognizer)
    try {
        $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
        $engine.SetInputToDefaultAudioDevice()
        $result = $engine.Recognize([TimeSpan]::FromSeconds(6))
        if ($result -and $result.Confidence -ge 0.55) { $result.Text }
    } finally {
        $engine.Dispose()
    }
    """
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, encoding="utf-8", errors="replace", timeout=20,
    )
    if result.returncode == 2:
        print("Falta un motor de reconocimiento de voz en español compatible con Windows.")
    elif result.returncode:
        print("No pude iniciar el reconocimiento de voz. Comprueba el micrófono y el idioma.")
    return result.stdout.strip() if result.returncode == 0 else ""


HELP = """Escribe una orden o pulsa Intro para usar el micrófono.
  Mueve la pestaña VSCode a la mitad izquierda de la pantalla 1
  Pon el Explorador a la mitad derecha del monitor 2
  pantallas | ventanas | ayuda | salir"""


def execute(desktop, command):
    key = normalize(command)
    if key == "ayuda":
        return HELP
    if key == "pantallas":
        return "\n".join(
            f"{number}: {bounds}" + (" (principal)" if primary else "")
            for number, (bounds, primary) in sorted(desktop.screens().items())
        ) or "No encontré pantallas."
    if key == "ventanas":
        return "\n".join(
            f"{app_label(executable)} · {title}" if executable else title
            for _, title, executable in desktop.windows()
        ) or "No encontré ventanas."
    if move := parse_move(command):
        return desktop.move(*move)
    return "Todavía no sé hacer eso. Escribe «ayuda» para ver las órdenes disponibles."


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 o 11 para controlar el escritorio.")
        return 1
    desktop = Desktop()
    print("JARVIS\n" + HELP)
    while True:
        try:
            command = input("\nTú > ").strip()
            if not command:
                print("Escuchando…")
                command = listen()
                if not command:
                    print("Puedes repetir la orden o escribirla.")
                    continue
                print(f"Te entendí: {command}")
                if input("¿Ejecutar? [s/N] ").strip().lower() != "s":
                    continue
            key = normalize(command)
            if key == "salir":
                return 0
            print(execute(desktop, command))
        except (EOFError, KeyboardInterrupt):
            return 0
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"No se pudo completar la orden: {error}")


if __name__ == "__main__":
    sys.exit(main())
