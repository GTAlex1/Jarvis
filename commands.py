"""Spanish command parsing and window geometry, independent of Win32."""
import re
import unicodedata

from wake_word import WAKE_WORD
WAKE_PREFIX = re.compile(r"^(?:oye )?" + re.escape(WAKE_WORD.casefold()) + r"[, ]+")


def clean(value):
    value = "".join(ch for ch in unicodedata.normalize("NFD", value.lower())
                    if not unicodedata.combining(ch))
    value = " ".join(value.strip().rstrip(".!?").split())
    return WAKE_PREFIX.sub("", value)


# Keep corrections explicit so an application name is never guessed.
POSITIONS = {
    "izquierda": "left", "izquieda": "left", "derecha": "right",
    "arriba": "top", "superior": "top", "abajo": "bottom", "inferior": "bottom",
    "arriba izquierda": "top_left", "superior izquierda": "top_left",
    "izquierda arriba": "top_left", "arriba derecha": "top_right",
    "superior derecha": "top_right", "derecha arriba": "top_right",
    "abajo izquierda": "bottom_left", "inferior izquierda": "bottom_left",
    "izquierda abajo": "bottom_left", "abajo derecha": "bottom_right",
    "inferior derecha": "bottom_right", "derecha abajo": "bottom_right",
    "centro": "center", "centrado": "center",
    "pantalla completa": "full", "maximizado": "full", "maximizada": "full",
}
POSITION_PATTERN = "|".join(re.escape(name) for name in sorted(POSITIONS, key=len, reverse=True))
SCREEN = re.compile(r" (?:(?:a|en|de) (?:la |el )?|al |del )?(?:pantalla|monitor) (\d+|principal)$")
ACTIONS = {
    "abre": "open", "abrir": "open", "inicia": "open",
    "cierra": "close", "cerrar": "close",
    "minimiza": "minimize", "minimizar": "minimize",
    "restaura": "restore", "restaurar": "restore",
    "enfoca": "focus", "enfocar": "focus", "activa": "focus",
    "maximiza": "maximize", "maximizar": "maximize",
    "centra": "center", "centrar": "center",
}
SYSTEM_COMMANDS = {
    "apaga el ordenador": "shutdown", "apaga el equipo": "shutdown", "apaga el pc": "shutdown",
    "apagar el ordenador": "shutdown", "apagar el equipo": "shutdown",
    "reinicia el ordenador": "restart", "reinicia el equipo": "restart", "reinicia el pc": "restart",
    "reiniciar el ordenador": "restart", "reiniciar el equipo": "restart",
    "muestra el escritorio": "desktop", "mostrar escritorio": "desktop",
    "escritorio": "desktop",
    "minimiza todo": "minimize_all", "minimiza todas las ventanas": "minimize_all",
    "restaura todas las ventanas": "restore_all",
    "vista de tareas": "task_view",
    "bloquea el equipo": "lock", "bloquear equipo": "lock", "bloquea el pc": "lock",
    "sube el volumen": "volume_up", "sube volumen": "volume_up",
    "baja el volumen": "volume_down", "baja volumen": "volume_down",
    "silencia": "mute", "silenciar": "mute", "silencia el sonido": "mute",
    "silencia o activa el sonido": "mute", "mute": "mute",
    "pausa musica": "play_pause", "pausa la musica": "play_pause",
    "reproduce musica": "play_pause", "reproducir o pausar": "play_pause",
    "siguiente cancion": "next_track", "anterior cancion": "previous_track",
    "captura de pantalla": "screenshot", "recorte de pantalla": "screenshot",
    "captura toda la pantalla": "screenshot_full", "haz una captura de toda la pantalla": "screenshot_full",
}
SPOKEN_NUMBERS = ("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez")
SPOKEN_SCREEN = re.compile(r" (?:pantalla|monitor) (" + "|".join(SPOKEN_NUMBERS) + r")$")
LIST_COMMANDS = {
    "ventanas": "windows", "lista ventanas": "windows",
    "aplicaciones": "apps", "programas": "apps", "lista aplicaciones": "apps",
    "pantallas": "screens", "monitores": "screens", "lista pantallas": "screens",
    "ayuda": "help", "ayudame": "help", "dime como puedes ayudarme": "help",
    "que puedes hacer": "help", "comandos": "help", "salir": "exit",
}


def target_name(value):
    return re.sub(r"^(?:(?:el|la) )?(?:(?:ventana|pestana)(?: de)? )?(?:el |la )?", "", value).strip()


def parse(command):
    value = clean(command)
    if value in LIST_COMMANDS:
        return (LIST_COMMANDS[value],)
    if value in SYSTEM_COMMANDS:
        return "system", SYSTEM_COMMANDS[value]
    if match := SPOKEN_SCREEN.search(value):
        value = value[:match.start(1)] + str(SPOKEN_NUMBERS.index(match[1]) + 1)
    screen = None
    if match := SCREEN.search(value):
        screen = 0 if match[1] == "principal" else int(match[1])
        if match[1] != "principal" and screen < 1:
            return None
        value = value[:match.start()]
    verb, _, argument = value.partition(" ")
    if verb in ACTIONS and argument:
        action = ACTIONS[verb]
        title = target_name(argument)
        if not title:
            return None
        if action in {"maximize", "center"}:
            return "place", title, "full" if action == "maximize" else "center", screen
        if screen is not None:
            return None
        return action, title

    value = re.sub(r"^(?:mueve|mover|pon|poner|coloca|colocar) ", "", value)
    match = re.fullmatch(
        rf"(.+?) (?:(?:a|en) (?:la |el )?|al )?(?:(?:la |el )?(?:mitad|esquina|parte) )?({POSITION_PATTERN})",
        value,
    )
    if match:
        title = target_name(match[1])
        if title:
            return "place", title, POSITIONS[match[2]], screen
    if screen is not None and target_name(value):
        return "place", target_name(value), "monitor", screen
    return None


def rectangle(bounds, position, size):
    left, top, right, bottom = bounds
    mid_x, mid_y = left + (right-left)//2, top + (bottom-top)//2
    cells = {
        "left": (left, top, mid_x, bottom), "right": (mid_x, top, right, bottom),
        "top": (left, top, right, mid_y), "bottom": (left, mid_y, right, bottom),
        "top_left": (left, top, mid_x, mid_y), "top_right": (mid_x, top, right, mid_y),
        "bottom_left": (left, mid_y, mid_x, bottom), "bottom_right": (mid_x, mid_y, right, bottom),
    }
    if position in cells:
        x, y, r, b = cells[position]
        return x, y, r-x, b-y
    width, height = min(size[0], right-left), min(size[1], bottom-top)
    if position in {"center", "monitor"}:
        return left + (right-left-width)//2, top + (bottom-top-height)//2, width, height
    if position == "full":
        return left, top, width, height
    raise ValueError("Posición desconocida.")


HELP = """VENTANAS
abre VSCode · cierra Chrome · restaura Firefox · enfoca Spotify
minimiza Chrome · maximiza VSCode · centra el Explorador

POSICIONES
VSCode izquierda · Chrome derecha monitor 2
Firefox arriba · Bloc de notas abajo
VSCode esquina superior izquierda · Chrome esquina inferior derecha
Firefox arriba derecha · Explorador abajo izquierda
mueve VSCode a la pantalla 2 · VSCode pantalla completa
Añade «pantalla principal» o «monitor 2» a cualquier posición.

WINDOWS
abre configuración · abre administrador de tareas · abre descargas
abre documentos · abre explorador · abre calculadora
escritorio · vista de tareas · minimiza todo · restaura todas las ventanas
captura de pantalla · bloquea el equipo
apaga el equipo · reinicia el equipo · cancela

MULTIMEDIA
sube volumen · baja volumen · silencia o activa el sonido
reproducir o pausar · siguiente canción · anterior canción

CONSULTAS
ventanas · aplicaciones · pantallas · ayuda · salir

Si hay varias ventanas, usa un título más específico.
Cerrar solicita el cierre normal y permite que la aplicación pregunte si quieres guardar.
Escritorio, sonido y reproducción alternan su estado como las teclas de Windows.
Pantalla completa maximiza la ventana. El recorte abre la selección de Windows."""
