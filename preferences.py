"""Current-user settings for the Windows desktop and console entry points."""
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SETTINGS_KEY = r"Software\JARVIS"
APP_NAME = "JARVIS"


def startup_command(executable, script=None):
    # Windows paths cannot contain double quotes. Quote every path, even if it
    # currently contains no spaces, and avoid any shell or search-path lookup.
    paths = (executable,) if script is None else (executable, script)
    command = " ".join(f'"{path}"' for path in paths) + " --background"
    if len(command.encode("utf-16-le")) // 2 >= 260:
        raise ValueError("La ruta es demasiado larga para el inicio automático de Windows.")
    return command


def current_startup_command():
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return startup_command(executable)
    windowed = executable.with_name("pythonw.exe")
    if not windowed.is_file():
        raise OSError("No se encontró pythonw.exe para iniciar JARVIS sin consola.")
    return startup_command(windowed, Path(__file__).with_name("jarvis_gui.py").resolve())


def read_value(path, name, default):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return default


def starts_with_windows():
    return bool(read_value(RUN_KEY, APP_NAME, ""))


def set_startup(enabled):
    import winreg

    if enabled:
        command = current_startup_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass


def microphone_enabled():
    return read_value(SETTINGS_KEY, "MicrophoneEnabled", 1) == 1


def set_microphone(enabled):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "MicrophoneEnabled", 0, winreg.REG_DWORD, int(enabled))
