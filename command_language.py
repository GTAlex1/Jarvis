"""Conservative Spanish intent normalization and phonetic ranking for spoken names."""
from difflib import SequenceMatcher
import re
import unicodedata

from commands import WAKE_PREFIX, target_name

# Group exact verb surfaces by intent. Clitics are stripped only when the
# resulting form belongs to a known verb.
VERBS = {
    "abre": ("abre", "abrir", "abrire", "abrase", "arranca", "arrancar", "iniciar", "inicia", "ejecuta", "ejecutar"),
    "cierra": ("cierra", "cerra", "cerrar", "cerrare", "cierre", "cierres", "quita", "quitar"),
    "minimiza": ("minimiza", "minimizar", "minimizare", "minimice"),
    "maximiza": ("maximiza", "maximizar", "maximizare", "maximice"),
    "restaura": ("restaura", "restaurar", "restaurare", "restaure"),
    "enfoca": ("enfoca", "enfocar", "enfocare", "enfoque", "activar", "activa"),
    "centra": ("centra", "centrar", "centrare", "centre"),
    "mueve": ("mueve", "mover", "movere", "mueva", "colocar", "coloca"),
    "pon": ("pon", "poner", "pone"),
    "reinicia": ("reinicia", "reiniciar", "reinicie", "reiniciare"),
    "apaga": ("apaga", "apagar", "apague", "apagare"),
}
VARIANTS = {form: verb for verb, forms in VERBS.items() for form in forms}
CLITIC = re.compile(r"(?:melo|mela|melos|melas|me|nos|lo|la)$")
UNSAFE = re.compile(r"\b(?:no|nunca|jamas|excepto|quizas|cuando|si acaso|a lo mejor|y luego|"
                    r"imagina|supongamos|dijiste|dijo|dije|dice|dicen|dile|digan|decir|por ejemplo|"
                    r"podria|deberia|deberias|habria|en caso de|voy a|iba a)\b")
REQUEST = re.compile(r"^(?:(?:puedes|podrias|quiero que|por favor|porfa|me puedes|me podrias)"
                     r"[, ]+)+")
PLACEMENT = re.compile(r"\b(?:izquierda|derecha|esquina|mitad|monitor|pantalla|centro|arriba|abajo)\b")
POWER_TARGETS = {"ordenador", "equipo", "pc", "computadora", "computador", "compu", "ordenador de nuevo"}
CALCULATOR = {"calculo", "calculadora", "calculadora de windows", "calculadora windows", "calculator"}
REACTIONS = {"no", "no gracias", "no, gracias", "si", "si por favor", "si, confirma la orden"}


def simplify(text):
    return "".join(char for char in unicodedata.normalize("NFD", text.casefold())
                   if not unicodedata.combining(char))


def normalize_order(text):
    if any(char in text for char in ('"', "«", "»", "“", "”")):
        return ""
    original = " ".join(simplify(text).strip().split())
    text = WAKE_PREFIX.sub("", original.strip(" ¿?¡!.,"))
    if text in REACTIONS:
        return text
    if UNSAFE.search(text):
        return ""
    requested = REQUEST.match(text)
    if "?" in original and not requested and text != "que puedes hacer":
        return ""
    text = REQUEST.sub("", text)
    text = re.sub(r"[, ]+por favor$|[, ]+porfa$", "", text).strip()
    word, separator, target = text.partition(" ")
    base = VARIANTS.get(word) or VARIANTS.get(CLITIC.sub("", word), word)
    if base == "pon":
        base = "mueve" if PLACEMENT.search(target) else "abre"
    if base in {"reinicia", "apaga"}:
        if target_name(target) not in POWER_TARGETS:
            return ""
        # ASR corrections for destructive actions must be explicit lexical
        # variants, never a fuzzy match to an arbitrary system command.
        return f"{base} el equipo"
    if base == "cierra" and re.fullmatch(r"[^,;]+, pero deja [^,;]+ abierto", target):
        return f"{base} {target}"
    if " si " in f" {target} " or re.search(r"[,;]|\b(?:o|y) (?:abre|cierra|apaga|reinicia)\b", target):
        return "" if text != "silencia o activa el sonido" else text
    if base == "abre" and target_name(target) in CALCULATOR:
        return "abre calculadora"
    return base + separator + target


def phonetic_key(text):
    text = simplify(text)
    for pattern, replacement in (
        (r"league\b|leag\b", "lig"), (r"ck|qu", "k"), (r"ph", "f"),
        (r"sh|ch", "x"), (r"ce|ci", "s"), (r"c", "k"), (r"z", "s"),
        (r"v", "b"), (r"h", ""), (r"y", "i"), (r"ee|ea", "i"), (r"ght", "t"),
        (r"\bes(?=p[ot])", "s"), (r"w", "u"), (r"r{2,}", "r"),
    ):
        text = re.sub(pattern, replacement, text)
    return re.sub(r"[^a-z0-9]", "", text)


def phonetic_score(query, label):
    a, b = phonetic_key(query), phonetic_key(label)
    if min(len(a), len(b)) < 4:
        return 0.0
    if a == b:
        return 1.0
    if b.startswith(a):
        return max(0.76, len(a) / len(b))
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def rank_targets(query, items, labels, limit=5):
    ranked = [(max((phonetic_score(query, label) for label in labels(item)), default=0.0), item)
              for item in items]
    ranked.sort(key=lambda result: result[0], reverse=True)
    if not ranked:
        return ()
    floor = max(0.70, ranked[0][0] - 0.14)
    return tuple(item for score, item in ranked[:limit] if score >= floor)
