"""Portable classification and policy for commands issued by voice."""
from dataclasses import dataclass, field
from types import MappingProxyType

ALLOW, VERBAL, BUTTON, HOTKEY, CODE, BLOCK = "allow", "verbal", "button", "hotkey", "code", "block"
METHODS = {
    ALLOW: "Sin confirmación", VERBAL: "Confirmación verbal", BUTTON: "Botón local",
    HOTKEY: "Ctrl + Alt + F10", CODE: "Código temporal", BLOCK: "Bloquear",
}


@dataclass(frozen=True)
class Category:
    label: str
    risk: str
    remote: bool = False
    reversible: bool = True
    require_local: bool = False


CATEGORIES = {
    "query": Category("Consultas", "bajo"),
    "open": Category("Abrir aplicaciones", "bajo"),
    "close": Category("Cerrar aplicaciones o JARVIS", "intermedio", reversible=False),
    "window": Category("Gestionar ventanas", "bajo"),
    "media": Category("Control multimedia", "bajo"),
    "volume": Category("Control de volumen", "bajo"),
    "screenshot": Category("Capturas locales", "intermedio", reversible=False),
    "lock": Category("Bloquear Windows", "intermedio"),
    "power": Category("Apagar y reiniciar", "alto", reversible=False),
    "files": Category("Gestión de archivos", "alto", reversible=False),
    "transfer": Category("Transferencia de información", "crítico", remote=True, reversible=False, require_local=True),
    "shell": Category("Ejecución de comandos externos", "crítico", reversible=False, require_local=True),
    "administration": Category("Herramientas administrativas", "alto"),
    "security": Category("Configurar seguridad o elevar privilegios", "crítico", require_local=True),
    "integration": Category("Integraciones con aplicaciones", "variable", reversible=False),
    "remote": Category("Control y permisos remotos", "crítico", remote=True, reversible=False, require_local=True),
}
ADMIN_NAMES = {
    "administrador de tareas", "task manager", "configuracion", "settings", "ajustes",
    "windows update", "configuracion de pantalla", "configuracion de sonido", "wifi",
    "bluetooth", "panel de control", "control panel", "terminal", "windows terminal",
    "powershell", "windows powershell", "simbolo del sistema", "command prompt", "regedit",
    "editor del registro", "administracion de equipos", "computer management",
}
LOCAL = {BUTTON, HOTKEY, CODE, BLOCK}
PRESETS = {
    "Libertad": dict(files=VERBAL, transfer=BLOCK, shell=BLOCK, administration=BUTTON, security=BUTTON, remote=BLOCK),
    "Equilibrado": dict(close=VERBAL, screenshot=VERBAL, lock=VERBAL, power=VERBAL,
                        files=BUTTON, administration=BUTTON, security=BUTTON, transfer=BLOCK, shell=BLOCK, remote=BLOCK),
    "Estricto": dict(close=CODE, screenshot=CODE, lock=CODE, power=CODE, files=CODE,
                     administration=CODE, security=CODE, integration=BUTTON, transfer=BLOCK, shell=BLOCK, remote=BLOCK),
}


@dataclass(frozen=True)
class SecurityPolicy:
    mode: str = "Equilibrado"
    biometrics: bool = True
    rules: object = field(default_factory=dict)

    def __post_init__(self):
        if self.mode not in (*PRESETS, "Personalizado") or type(self.biometrics) is not bool:
            raise ValueError("Perfil de seguridad no válido.")
        if not isinstance(self.rules, (dict, MappingProxyType)) or any(
            key not in CATEGORIES or value not in METHODS for key, value in self.rules.items()
        ):
            raise ValueError("Permisos no válidos.")
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))

    def method(self, category):
        if category not in CATEGORIES:
            return BLOCK
        base = PRESETS.get(self.mode, PRESETS["Equilibrado"])
        method = self.rules.get(category, base.get(category, ALLOW)) if self.mode == "Personalizado" else base.get(category, ALLOW)
        if CATEGORIES[category].require_local and method not in LOCAL:
            return BUTTON
        return method

    def serialized(self):
        return {"version": 1, "mode": self.mode, "biometrics": self.biometrics, "rules": dict(self.rules)}

    @classmethod
    def from_saved(cls, data):
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Formato de seguridad desconocido.")
        return cls(data["mode"], data["biometrics"], data["rules"])


def classify(intent, selected_label=""):
    action = intent[0]
    if action == "open":
        return "administration" if {intent[1], selected_label} & ADMIN_NAMES else "open"
    if action == "system":
        effect = intent[1]
        if effect in {"volume_up", "volume_down", "mute"}:
            return "volume"
        if effect in {"play_pause", "next_track", "previous_track"}:
            return "media"
        if effect.startswith("screenshot"):
            return "screenshot"
        if effect == "lock":
            return "lock"
        if effect in {"shutdown", "restart"}:
            return "power"
        return "window" if effect in {"desktop", "task_view", "minimize_all", "restore_all"} else "unknown"
    if action in {"apps", "windows", "screens", "help"}:
        return "query"
    if action in {"close", "exit"}:
        return "close"
    if action in {"place", "minimize", "restore", "focus"}:
        return "window"
    return action
