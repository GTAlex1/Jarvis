"""Conservative Spanish intent normalization and phonetic ranking for spoken names."""
from difflib import SequenceMatcher
import re
import unicodedata

from commands import WAKE_PREFIX

VERBS = {
    "abre": ("abrir", "abrire", "abreme", "abrase", "arranca", "arrancar", "iniciar", "inicia", "ejecuta"),
    "cierra": ("cerrar", "cerrare", "cierrame", "cierre", "cierres", "cerralo"),
    "minimiza": ("minimizar", "minimizare", "minimice", "minimizame"),
    "maximiza": ("maximizar", "maximizare", "maximice", "maximizame"),
    "restaura": ("restaurar", "restaurare", "restaure"),
    "enfoca": ("enfocar", "enfocare", "enfoque", "activar", "activa"),
    "centra": ("centrar", "centrare", "centre"),
    "mueve": ("mover", "movere", "mueveme", "mueva", "colocar", "coloca", "poner", "pon"),
}
VARIANTS = {form: verb for verb, forms in VERBS.items() for form in forms}
UNSAFE = re.compile(r"\b(?:no|nunca|jamas|excepto|quizas|si puedes luego|a lo mejor)\b")
REQUEST = re.compile(r"^(?:(?:puedes|podrias|quiero que|por favor|me puedes)\s+)+")


def simplify(text):
    return "".join(char for char in unicodedata.normalize("NFD", text.casefold())
                   if not unicodedata.combining(char))


def normalize_order(text):
    text = " ".join(simplify(text).strip(" ¿?¡!.,").split())
    text = WAKE_PREFIX.sub("", text)
    text = REQUEST.sub("", text)
    text = re.sub(r"[, ]+por favor$", "", text).strip()
    if UNSAFE.search(text) and text not in {"no", "no gracias", "no, gracias"}:
        return ""
    word, separator, target = text.partition(" ")
    # Keep multiword desktop shortcuts, such as «minimiza todo», intact.
    return VARIANTS.get(word, word) + separator + target


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
