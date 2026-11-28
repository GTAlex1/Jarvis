"""Current-user settings for the Windows desktop and console entry points."""
from dataclasses import asdict, dataclass, fields, replace
import json
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



CAPTURE_INTERFACES = {
    "Automática": "", "MME": "MME", "DirectSound": "Windows DirectSound",
    "WASAPI": "Windows WASAPI", "ASIO": "ASIO",
}


@dataclass(frozen=True)
class VoiceSettings:
    enabled: bool = False
    device: str = ""
    voice: str = ""
    volume: int = 75
    sensitivity: int = 3
    interface: str = ''
    conversational: bool = True
    context_seconds: int = 25
    reply_seconds: int = 8
    speech_detail: str = "normal"
    speaker_threshold: int = 72
    language: str = "es"
    playback_guard: bool = True

    def __post_init__(self):
        if type(self.playback_guard) is not bool:
            raise ValueError("Protección de reproducción no válida.")
        if self.language not in {"es", "en"}:
            raise ValueError("Idioma de reconocimiento no válido.")
        if type(self.enabled) is not bool or not isinstance(self.device, str) or not isinstance(self.voice, str):
            raise ValueError("Configuración de voz no válida.")
        if type(self.speaker_threshold) is not int or not 65 <= self.speaker_threshold <= 90:
            raise ValueError("La exigencia de voz debe estar entre 65 y 90.")
        if type(self.conversational) is not bool:
            raise ValueError("Modo conversacional no válido.")
        if type(self.context_seconds) is not int or not 5 <= self.context_seconds <= 120:
            raise ValueError("La duración del contexto debe estar entre 5 y 120 segundos.")
        if type(self.reply_seconds) is not int or not 3 <= self.reply_seconds <= 18:
            raise ValueError("La espera de respuesta debe estar entre 3 y 18 segundos.")
        if self.speech_detail not in ("breve", "normal", "ampliado"):
            raise ValueError("Nivel de detalle no válido.")
        if self.interface not in CAPTURE_INTERFACES.values():
            raise ValueError("Interfaz de captura no válida.")
        if type(self.volume) is not int or not 0 <= self.volume <= 100:
            raise ValueError("El volumen debe estar entre 0 y 100.")
        if type(self.sensitivity) is not int or not 1 <= self.sensitivity <= 5:
            raise ValueError("La sensibilidad debe estar entre 1 y 5.")


def voice_settings():
    options = VoiceSettings()
    try:
        saved = json.loads(read_value(SETTINGS_KEY, "VoiceSettings", "{}"))
    except (TypeError, ValueError):
        return options
    if isinstance(saved, dict):
        for field in fields(options):
            if field.name in saved:
                try:
                    options = replace(options, **{field.name: saved[field.name]})
                except ValueError:
                    continue
    return options


def save_voice_settings(settings):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "VoiceSettings", 0, winreg.REG_SZ, json.dumps(asdict(settings)))


def security_settings():
    from permissions import BLOCK, CATEGORIES, SecurityPolicy

    raw = read_value(SETTINGS_KEY, "SecuritySettings", None)
    if raw is None:
        # 0.6.4 required codes. Preserve that protection for existing voice users.
        legacy = read_value(SETTINGS_KEY, "VoiceSettings", None)
        return SecurityPolicy("Estricto" if legacy is not None else "Equilibrado")
    try:
        return SecurityPolicy.from_saved(json.loads(raw))
    except (TypeError, ValueError, KeyError):
        return SecurityPolicy("Personalizado", True, dict.fromkeys(CATEGORIES, BLOCK))


def save_security_settings(policy):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "SecuritySettings", 0, winreg.REG_SZ, json.dumps(policy.serialized()))


def adaptation_settings():
    from voice_adaptation import Adaptation

    try:
        saved = json.loads(read_value(SETTINGS_KEY, "VoiceAdaptation", "{}"))
        return Adaptation(saved.get("enabled", False), tuple(tuple(item) for item in saved.get("aliases", ())))
    except (AttributeError, TypeError, ValueError, IndexError):
        return Adaptation()


def save_adaptation_settings(adaptation):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "VoiceAdaptation", 0, winreg.REG_SZ, json.dumps(asdict(adaptation)))


def application_folders():
    try:
        data = json.loads(read_value(SETTINGS_KEY, "ApplicationFolders", "[]"))
    except (OSError, TypeError, ValueError):
        return ()
    return tuple(item for item in data[:24] if isinstance(item, str)) if isinstance(data, list) else ()


def save_application_folders(folders):
    import winreg
    if len(folders) > 24:
        raise ValueError("Puedes añadir hasta 24 carpetas al catálogo.")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "ApplicationFolders", 0, winreg.REG_SZ, json.dumps(folders))


def update_channel():
    value = read_value(SETTINGS_KEY, "UpdateChannel", "stable")
    return value if value in ("stable", "experimental") else "stable"


def save_update_channel(value):
    import winreg

    if value not in ("stable", "experimental"):
        raise ValueError("Canal de actualizaciones desconocido.")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "UpdateChannel", 0, winreg.REG_SZ, value)


def lifecycle_settings():
    from lifecycle import LifecycleSettings

    try:
        data = json.loads(read_value(SETTINGS_KEY, "LauncherLifecycle", "{}"))
        return LifecycleSettings(data.get("enabled") is True,
                                 tuple(value for value in data.get("providers", ()) if isinstance(value, str)),
                                 tuple(value for value in data.get("games", ()) if isinstance(value, str)))
    except (OSError, ValueError, TypeError, AttributeError):
        return LifecycleSettings()


def save_lifecycle_settings(settings):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SETTINGS_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "LauncherLifecycle", 0, winreg.REG_SZ, json.dumps(asdict(settings)))
