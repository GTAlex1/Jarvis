"""Temporary, deterministic dialogue and spoken rendering for JARVIS."""
from dataclasses import dataclass
import re
from textwrap import wrap

from commands import SPOKEN_NUMBERS, WAKE_WORD, clean, parse
from permissions import BUTTON, CODE, HOTKEY, VERBAL
from voice_authorization import ApprovalAnswer, LocalApproval, PowerScheduled

STOP = {"para", "parate", "detente", "cancela", "cancelar", "cancelalo", "cancel", "stop"}
INTERRUPT_PHRASES = tuple(f"{WAKE_WORD.casefold()} {verb}" for verb in ("para", "cancela", "detente"))
NEXT = {"continua", "sigue", "siguiente", "dame mas detalles", "mas detalles", "mas",
        "dame un ejemplo", "un ejemplo", "ejemplo"}
YES = {"si", "si por favor", "vale", "de acuerdo", "claro", "yes", "yes please"}
NO = {"no", "no gracias"}
REPEAT = {"repite", "repitelo", "repite eso", "dilo otra vez", "otra vez"}
ORDINALS = ("primer", "segund", "tercer", "cuart", "quint", "sext", "septim", "octav", "noven", "decim")
PAGE_SIZE = {"breve": 2, "normal": 3, "ampliado": 5}
TOPIC_HELP = {
    "aplicaciones": (
        "Puedo abrir aplicaciones del menú Inicio, como Spotify o Visual Studio Code.",
        "Di, por ejemplo, «abre Spotify». Para escuchar las aplicaciones disponibles, di «lista aplicaciones».",
    ),
    "ventanas": (
        "Puedes mover, cerrar, minimizar, maximizar y organizar ventanas.",
        "Di «mueve Firefox a la izquierda», «minimiza Chrome» o «enfoca Spotify».",
        "Para organizar dos ventanas puedes colocar una a la izquierda y la otra a la derecha. "
        "También puedes usar las esquinas.",
    ),
    "monitores": (
        "Puedo mover una ventana a otro monitor, colocarla en una esquina o maximizarla.",
        "Di «mueve Firefox al monitor dos» o «Chrome derecha monitor dos». "
        "Para conocer tus monitores, di «lista pantallas».",
    ),
    "multimedia": (
        "Puedo subir o bajar el volumen, silenciar el equipo y controlar la reproducción.",
        "Di «sube el volumen», «pausa la música» o «siguiente canción».",
    ),
    "windows": (
        "Puedo abrir la configuración, mostrar el escritorio, hacer un recorte o bloquear el equipo.",
        "Di «abre configuración», «vista de tareas» o «captura de pantalla».",
    ),
}
TOPIC_ALIASES = {
    "apps": "aplicaciones", "programas": "aplicaciones", "pantallas": "monitores",
    "musica": "multimedia", "sonido": "multimedia", "sistema": "windows",
}


@dataclass(frozen=True)
class TargetOption:
    label: str
    target: tuple


@dataclass(frozen=True)
class Clarification:
    written: str
    options: tuple
    kind: str


@dataclass(frozen=True)
class SelectedCommand:
    command: str
    option: TargetOption


@dataclass(frozen=True)
class Turn:
    speech: str = ""
    command: str | SelectedCommand | ApprovalAnswer | None = None
    accepted: bool = True
    end: bool = False
    followup: bool = False


def split_speech(text, limit=145):
    """Keep each synthesis segment bounded and prefer natural pauses."""
    text = text.strip()
    if len(text) <= limit:
        return (text,) if text else ()
    return tuple(part for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text.strip())
                 for part in wrap(sentence, width=limit, break_on_hyphens=False) if part)


def spoken_pages(action, text, detail):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ()
    nouns = {"apps": "aplicaciones", "windows": "ventanas", "screens": "pantallas"}
    if action in nouns and not lines[0].startswith("No encontré"):
        if action == "screens":
            descriptions = []
            for line in lines:
                match = re.fullmatch(r"(\d+): \((-?\d+), (-?\d+), (-?\d+), (-?\d+)\)( \(principal\))?", line)
                if match:
                    num, x, y, right, bottom = map(int, match.groups()[:5])
                    main = ", principal" if match[6] else ""
                    line = f"pantalla {num}{main}, de {right-x} por {bottom-y}"
                descriptions.append(line)
            lines = descriptions
        size = PAGE_SIZE[detail]
        chunks = [", ".join(item.replace(" · ", ", ") for item in lines[i:i + size])
                  for i in range(0, len(lines), size)]
        prefix = f"Encontré {len(lines)} {nouns[action]}. " if len(lines) != 1 else "Encontré una. "
        return (prefix + chunks[0] + ".", *(part + "." for part in chunks[1:]))
    if len(lines) > 1:
        size = PAGE_SIZE[detail]
        pages = [" ".join(lines[i:i + size]) for i in range(0, len(lines), size)]
        return tuple(pages)
    return (lines[0],)


class Dialogue:
    def __init__(self, detail="normal", enabled=True):
        self.detail = detail
        self.enabled = enabled
        self.clear()

    def clear(self):
        self.expires = 0.0
        self.last = ""
        self.pages = ()
        self.position = 0
        self.help_topic = False
        self.pending = None
        self.verbal = None
        self.option_offset = 0

    def keep(self, now, seconds):
        if self.last:
            self.expires = now + seconds

    def expire(self, now):
        if self.expires and now >= self.expires:
            self.clear()

    def abandon_question(self):
        self.pending = None
        self.verbal = None

    def answer(self, command, result):
        if isinstance(result, PowerScheduled):
            self.clear()
            return Turn(speech=result.message, followup=True)
        if isinstance(result, LocalApproval):
            self.clear()
            if result.method == VERBAL:
                self.verbal = result.ticket
                self.last = f"¿Seguro? {result.description}. Di sí para confirmar o cancela."
                return Turn(speech=self.last, followup=True)
            instructions = {
                HOTKEY: "Pulsa Control, Alt y F10 para confirmar.",
                BUTTON: "Confirma la acción en la bandeja.",
                CODE: "Abre Confirmar acción de voz en la bandeja e introduce el código.",
            }
            return Turn(speech=instructions[result.method], end=True)
        if isinstance(result, Clarification):
            self.clear()
            if not self.enabled:
                return self.say("Di la orden de nuevo con el nombre exacto que te indico. " +
                                ", ".join(item.label for item in result.options[:3]) + ".")
            self.pending = (command, result)
            return self.options()
        source = command.command if isinstance(command, SelectedCommand) else command
        intent = parse(source)
        action = intent[0] if intent else ""
        self.clear()
        if action == "help":
            if not self.enabled:
                return self.say("Puedo abrir aplicaciones, organizar ventanas y controlar monitores, "
                                "multimedia y funciones de Windows. Por ejemplo, di «abre Spotify».")
            self.help_topic = True
            return self.present(
                ("Puedo controlar aplicaciones, ventanas, monitores, multimedia y funciones de Windows.",
                 *(f"{topic.capitalize()}. {pages[0]}" for topic, pages in TOPIC_HELP.items())),
                question="¿Sobre qué necesitas ayuda?",
            )
        return self.present(spoken_pages(action, str(result), self.detail))

    def present(self, pages, question=""):
        self.pages = pages
        self.position = 0
        return self.page(question)

    def say(self, text, accepted=True):
        self.last = text
        return Turn(speech=text, accepted=accepted)

    def page(self, question=""):
        if not self.pages:
            return self.say("")
        text = self.pages[self.position]
        if self.enabled and not question and self.position + 1 < len(self.pages):
            question = "¿Quieres que continúe?"
        return self.say(f"{text} {question}".strip())

    def options(self, reminder=""):
        _, result = self.pending
        count = len(result.options)
        if count == 1:
            label = result.options[0].label.strip()[:130]
            source, _ = self.pending
            action = (parse(source.command if isinstance(source, SelectedCommand) else source) or ("",))[0]
            if action == "close":
                return self.say(f"Encontré {label}. ¿Quieres cerrar esa ventana? Di sí o cancela.")
            return self.say(f"¿Te refieres a {label}? Di sí o repite el nombre.")
        choices = result.options[self.option_offset:self.option_offset + PAGE_SIZE[self.detail]]
        segments = []
        for i, item in enumerate(choices, self.option_offset):
            short = item.label.strip()[:130]
            segments.append(f"Opción {i + 1}, {short}.")
        prompt = reminder or (f"¿Te refieres a esta opción de {result.kind}?" if count == 1
                              else f"Encontré {count} opciones de {result.kind}.")
        ending = "Di el número o el nombre."
        if self.option_offset + len(choices) < count:
            ending += " También puedes decir continúa."
        return self.say(" ".join((prompt, *segments, ending)))

    def choose(self, key):
        command, result = self.pending
        key = re.sub(r"^(?:me refiero a |elige |quiero )", "", key)
        key = re.sub(r"[ ,]+por favor$", "", key)
        if len(result.options) == 1 and key in YES | {"si adelante", "si, adelante", "esa es", "ese es", "correcto", "yes"}:
            return SelectedCommand(command, result.options[0])
        value = re.sub(r"^(?:(?:la|el) |(?:opcion|numero) )+", "", key).strip()
        if value.isascii() and value.isdigit() and len(value) <= 4:
            number = int(value)
        else:
            number = next((i + 1 for i, word in enumerate(SPOKEN_NUMBERS) if value == word), 0)
            if not number:
                number = next((i + 1 for i, word in enumerate(ORDINALS) if value in
                               (word, word + "a", word + "o")), 0)
        if 1 <= number <= len(result.options):
            return SelectedCommand(command, result.options[number - 1])
        exact = [item for item in result.options if clean(item.label) == value]
        matches = exact or [item for item in result.options if value and value in clean(item.label)]
        if len(matches) == 1:
            return SelectedCommand(command, matches[0])
        return None

    def turn(self, text, now):
        self.expire(now)
        key = clean(text).strip("¿?¡!")
        if re.fullmatch(r"(?:si[, ]+)?continua(?: con (?:la explicacion|la respuesta|la lista))?", key):
            key = "continua"
        elif re.fullmatch(r"repite (?:lo que (?:has )?dicho|la ultima respuesta)", key):
            key = "repite"
        elif key in {"no, gracias", "cancela la conversacion", "cancela la orden", "para de hablar"}:
            key = "cancela"
        if self.verbal:
            if key in YES | {"si confirmo", "si confirmo la orden", "si, confirma la orden", "confirmo la orden", "confirm the action", "yes confirm the action"}:
                ticket = self.verbal
                self.clear()
                return Turn(command=ApprovalAnswer(ticket, True))
            if key in NO | STOP | {"no, cancela la orden", "no cancela la orden"}:
                ticket = self.verbal
                self.clear()
                return Turn(command=ApprovalAnswer(ticket, False))
            return Turn(speech="Di sí para confirmar esa acción, o cancela.", followup=True)
        if key in STOP or (key in NO and self.last):
            self.clear()
            return Turn(speech="De acuerdo.", end=True)
        if key in REPEAT:
            return Turn(speech=self.last or "Todavía no hay una respuesta que repetir.")
        if self.pending:
            if key in NEXT:
                count = len(self.pending[1].options)
                if self.option_offset + PAGE_SIZE[self.detail] < count:
                    self.option_offset += PAGE_SIZE[self.detail]
                return self.options()
            choice = self.choose(key)
            if choice is not None:
                self.pending = None
                return Turn(command=choice)
            return self.options("Dime qué opción quieres.")
        topic = TOPIC_ALIASES.get(key, key)
        if self.help_topic and topic in TOPIC_HELP:
            self.help_topic = False
            pages = TOPIC_HELP[topic]
            if self.detail == "ampliado":
                pages = (" ".join(pages[:2]), *pages[2:])
            return self.present(pages, "¿Quieres un ejemplo?" if len(pages) > 1 and self.detail != "ampliado" else "")
        if key in NEXT or key in YES:
            if self.position + 1 < len(self.pages):
                self.position += 1
                return self.page()
            return self.say("Ya te he dado toda la información." if self.pages else "Puedes decir otra orden.")
        if parse(text):
            return Turn(command=text)
        return Turn(speech="No he entendido la orden. Puedes decir ayuda.", accepted=False)
