"""Optional, explicitly managed aliases for recognized application names."""
from dataclasses import dataclass
import re

from command_language import UNSAFE, simplify
from commands import parse, target_name

MAX_ALIASES = 50
VALID_NAME = re.compile(r"[\w .:+&()'’-]{2,80}", re.UNICODE)
TARGET_VERBS = {"abre", "cierra", "minimiza", "enfoca", "restaura", "maximiza", "centra", "mueve"}


def name_key(text):
    return " ".join(simplify(text).split())


@dataclass(frozen=True)
class Adaptation:
    enabled: bool = False
    aliases: tuple = ()

    def __post_init__(self):
        if type(self.enabled) is not bool or len(self.aliases) > MAX_ALIASES:
            raise ValueError("Preferencias de adaptación no válidas.")
        keys = set()
        for variant, canonical in self.aliases:
            if not all(
                isinstance(name, str) and VALID_NAME.fullmatch(name) and not UNSAFE.search(name_key(name))
                and name_key(name) and name_key(name).split()[0] not in TARGET_VERBS
                for name in (variant, canonical)
            ):
                raise ValueError("Introduce nombres de aplicaciones, sin órdenes ni condiciones.")
            key = name_key(variant)
            if key in keys or key == name_key(canonical):
                raise ValueError("La pronunciación alternativa está repetida o coincide con el nombre.")
            keys.add(key)

    def apply(self, normalized):
        if not self.enabled or not self.aliases:
            return normalized
        intent = parse(normalized)
        verb, _, argument = normalized.partition(" ")
        if intent is None or verb not in TARGET_VERBS or intent[0] == "system":
            return normalized
        query = intent[1]
        for variant, canonical in self.aliases:
            if name_key(query) == name_key(variant):
                surface = target_name(argument)
                if surface == query or surface.startswith(query + " "):
                    return f"{verb} {name_key(canonical)}{surface[len(query):]}"
        return normalized
