import ctypes as c
from ctypes import wintypes as w
from pathlib import PureWindowsPath
import json
import os
import re
import subprocess
import sys
import unicodedata
from commands import HELP, clean, parse, rectangle


def normalize(value):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value.lower())
        if not unicodedata.combining(ch)
    ).strip().rstrip(".!?")


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
    parsed = parse(command)
    if parsed and parsed[0] == "place":
        _, title, position, screen = parsed
        legacy = {"left": "izquierda", "right": "derecha", "full": "completa"}
        return title, legacy.get(position, position), screen


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


def launch_matches(apps, query):
    names = {query}
    for executable, aliases in APP_NAMES.items():
        group = {normalize(alias) for alias in (executable, *aliases)}
        if query in group:
            names = group
            break
    exact = [app for app in apps if normalize(app[0]) in names]
    if exact:
        return exact
    return [app for app in apps if query in normalize(app[0])]


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
            "PostMessageW": ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
            "SetForegroundWindow": ([w.HWND], w.BOOL),
            "GetForegroundWindow": ([], w.HWND),
            "IsWindow": ([w.HWND], w.BOOL),
            "LockWorkStation": ([], w.BOOL),
            "keybd_event": ([w.BYTE, w.BYTE, w.DWORD, c.c_size_t], None),
            "GetShellWindow": ([], w.HWND),
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
        shell_window = self.api.GetShellWindow()

        @self.window_callback
        def collect(handle, _data):
            if handle != shell_window and self.api.IsWindowVisible(handle):
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

    def applications(self):
        script = """
        $ErrorActionPreference = 'Stop'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        ConvertTo-Json -InputObject @(Get-StartApps | Select-Object Name, AppID) -Compress
        """
        powershell = os.path.join(os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, encoding="utf-8-sig", timeout=12,
                creationflags=subprocess.CREATE_NO_WINDOW, check=True,
            )
            return sorted({
                (app["Name"], app["AppID"]) for app in json.loads(result.stdout)
                if app.get("Name") and app.get("AppID")
            }, key=lambda app: normalize(app[0]))
        except (subprocess.SubprocessError, ValueError) as error:
            raise OSError("Windows no pudo consultar las aplicaciones del menú Inicio.") from error

    def open_app(self, title):
        builtins = {
            "configuracion": "ms-settings:", "ajustes": "ms-settings:",
            "configuracion de pantalla": "ms-settings:display",
            "configuracion de sonido": "ms-settings:sound",
            "wifi": "ms-settings:network-wifi", "bluetooth": "ms-settings:bluetooth",
            "windows update": "ms-settings:windowsupdate",
            "descargas": "shell:Downloads", "documentos": "shell:Personal",
            "imagenes": "shell:My Pictures", "papelera": "shell:RecycleBinFolder",
        }
        executables = {
            "explorador": "explorer.exe", "explorador de archivos": "explorer.exe",
            "administrador de tareas": "System32/Taskmgr.exe",
            "bloc de notas": "System32/notepad.exe",
            "calculadora": "System32/calc.exe",
        }
        if title in builtins:
            os.startfile(builtins[title])
            return f"Solicité abrir «{title}»."
        if title in executables:
            os.startfile(os.path.join(os.environ["SystemRoot"], executables[title]))
            return f"Solicité abrir «{title}»."
        matches = launch_matches(self.applications(), title)
        if not matches:
            return f"No encontré «{title}» en el menú Inicio. Consulta «aplicaciones»."
        if len(matches) > 1:
            names = "\n".join(f"  {name}" for name, _ in matches)
            return f"Encontré varias aplicaciones. Usa su nombre completo:\n{names}"
        name, app_id = matches[0]
        if title == normalize("Explorador") or normalize(name) in {"explorador de archivos", "file explorer"}:
            os.startfile(os.environ["SystemRoot"] + r"\explorer.exe")
        else:
            os.startfile("shell:AppsFolder\\" + app_id)
        return f"Solicité a Windows que abriera «{name}»."

    def minimize(self, title):
        matches = matching_windows(self.windows(), title)
        if not matches:
            return f"No encontré ninguna ventana abierta que coincida con «{title}»."
        minimized = []
        failed = []
        for handle, name, _ in matches:
            if not self.api.IsIconic(handle):
                self.api.ShowWindow(handle, 6)  # SW_MINIMIZE
            (minimized if self.api.IsIconic(handle) else failed).append(name)
        lines = [f"Minimicé «{name}»." for name in minimized]
        lines.extend(f"No pude minimizar «{name}»." for name in failed)
        return "\n".join(lines)

    def select_window(self, title):
        matches = matching_windows(self.windows(), title)
        if not matches:
            raise ValueError(f"No encontré una ventana de «{title}». Puedes usar «abre {title}».")
        if len(matches) > 1:
            names = "\n".join(f"  {name}" for _, name, _ in matches)
            raise ValueError(f"Hay varias ventanas. Usa un título más específico:\n{names}")
        return matches[0]

    def window_action(self, action, title):
        handle, name, _ = self.select_window(title)
        if action == "close":
            if not self.api.PostMessageW(handle, 0x0010, 0, 0):  # WM_CLOSE
                raise c.WinError(c.get_last_error())
            return f"Solicité cerrar «{name}». Revisa si la aplicación pide guardar cambios."
        if action == "restore":
            self.api.ShowWindow(handle, 9)
            if self.api.IsIconic(handle) or self.api.IsZoomed(handle):
                return f"«{name}» no pudo restaurarse."
            return f"Restauré «{name}»."
        if action == "focus":
            if self.api.IsIconic(handle):
                self.api.ShowWindow(handle, 9)
            self.api.SetForegroundWindow(handle)
            if self.api.GetForegroundWindow() == handle:
                return f"«{name}» está en primer plano."
            return f"Windows impidió poner «{name}» en primer plano. Selecciónala desde la barra de tareas."
        raise ValueError("Acción de ventana desconocida.")

    def move(self, title, side, screen):
        position = {"izquierda": "left", "derecha": "right", "completa": "full"}.get(side, side)
        screens = self.screens()
        if screen in (None, 0):
            screen = next((number for number, (_, primary) in screens.items() if primary), None)
        if screen not in screens:
            return "No encontré esa pantalla. Escribe «pantallas» para ver las disponibles."
        handle, name, _ = self.select_window(title)
        was_maximized = self.api.IsZoomed(handle)
        if was_maximized or self.api.IsIconic(handle):
            self.api.ShowWindow(handle, 9)
        old = w.RECT()
        if not self.api.GetWindowRect(handle, c.byref(old)):
            raise c.WinError(c.get_last_error())
        target = rectangle(screens[screen][0], position, (old.right-old.left, old.bottom-old.top))
        if not self.api.SetWindowPos(handle, None, *target, 0x0014):
            raise c.WinError(c.get_last_error())
        if position == "full" or (position == "monitor" and was_maximized):
            self.api.ShowWindow(handle, 3)
            if self.api.IsZoomed(handle):
                return f"Maximicé «{name}» en la pantalla {screen}."
            return f"«{name}» no admitió maximizarse en la pantalla {screen}."
        actual = w.RECT()
        if not self.api.GetWindowRect(handle, c.byref(actual)):
            raise c.WinError(c.get_last_error())
        measured = (actual.left, actual.top, actual.right-actual.left, actual.bottom-actual.top)
        if measured != target:
            return f"Moví «{name}», pero su tamaño o posición quedó en {measured} frente al área solicitada {target}."
        return f"Coloqué «{name}» en la pantalla {screen}."

    def system_action(self, action):
        if action == "lock":
            if not self.api.LockWorkStation():
                raise c.WinError(c.get_last_error())
            return "Solicité bloquear la sesión de Windows."
        shortcuts = {
            "desktop": (0x5B, 0x44), "task_view": (0x5B, 0x09),
            "minimize_all": (0x5B, 0x4D), "restore_all": (0x5B, 0x10, 0x4D),
            "screenshot": (0x5B, 0x10, 0x53),
            "volume_up": (0xAF,), "volume_down": (0xAE,), "mute": (0xAD,),
            "play_pause": (0xB3,), "next_track": (0xB0,), "previous_track": (0xB1,),
        }
        keys = shortcuts[action]
        try:
            for key in keys:
                self.api.keybd_event(key, 0, 0, 0)
        finally:
            for key in reversed(keys):
                self.api.keybd_event(key, 0, 0x0002, 0)
        labels = {
            "desktop": "alternar el escritorio", "task_view": "abrir la vista de tareas",
            "minimize_all": "minimizar todas las ventanas", "restore_all": "restaurar las ventanas minimizadas en conjunto",
            "screenshot": "seleccionar un recorte de pantalla", "volume_up": "subir un paso el volumen",
            "volume_down": "bajar un paso el volumen", "mute": "alternar el silencio",
            "play_pause": "alternar reproducción y pausa", "next_track": "pasar a la siguiente pista",
            "previous_track": "volver a la pista anterior",
        }
        return f"Envié a Windows la orden de {labels[action]}."


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


def execute(desktop, command):
    parsed = parse(command)
    if not parsed:
        return "No entendí la orden. Escribe «ayuda» para ver los comandos disponibles."
    action, *args = parsed
    try:
        if action == "help":
            return HELP
        if action == "screens":
            return "\n".join(
                f"{number}: {bounds}" + (" (principal)" if primary else "")
                for number, (bounds, primary) in sorted(desktop.screens().items())
            ) or "No encontré pantallas."
        if action == "windows":
            return "\n".join(
                f"{app_label(executable)} · {title}" if executable else title
                for _, title, executable in desktop.windows()
            ) or "No encontré ventanas."
        if action == "apps":
            return "\n".join(name for name, _ in desktop.applications()) or "No encontré aplicaciones en el menú Inicio."
        if action == "open":
            return desktop.open_app(*args)
        if action == "minimize":
            return desktop.minimize(*args)
        if action == "place":
            return desktop.move(*args)
        if action == "system":
            return desktop.system_action(*args)
        if action == "exit":
            return "Cierra JARVIS desde su ventana o escribe «salir» en la consola."
        return desktop.window_action(action, *args)
    except ValueError as error:
        return str(error)


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 o 11 para controlar el escritorio.")
        return 1
    desktop = Desktop()
    print("JARVIS · Pulsa Intro con la línea vacía para dictar.\n" + HELP)
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
