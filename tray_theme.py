"""Technology mascot artwork and labels for the Windows status icon."""
from pathlib import Path

ICONS = Path(__file__).resolve().parent / "assets" / "tray"
THEMES = {
    "waiting": ("waiting", "En espera"),
    "listening": ("listening", "Escuchando"),
    "followup": ("listening", "Escuchando"),
    "starting": ("processing", "Preparando micrófono"),
    "processing": ("processing", "Procesando orden"),
    "executing": ("executing", "Ejecutando acción"),
    "speaking": ("executing", "Respondiendo"),
    "disabled": ("muted", "Escucha desactivada"),
    "muted": ("muted", "Micrófono desactivado"),
    "unavailable": ("error", "Error de voz"),
    "profiles": ("error", "Falta un perfil de voz"),
    "profile_damaged": ("error", "Error de perfil de voz"),
    "voice_rejected": ("error", "Voz sin autorización"),
    "voice_error": ("error", "Error de verificación"),
    "voice_quality": ("error", "Audio insuficiente"),
    "voice_short": ("error", "Muestra de voz insuficiente"),
}


def appearance(state):
    icon, label = THEMES.get(state, THEMES["unavailable"])
    return icon, f"JARVIS · {label}"
