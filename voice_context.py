"""A bounded second pass for installed names. It never creates an action."""
from difflib import SequenceMatcher
import json
import re

from command_language import phonetic_key, phonetic_score, simplify

TARGET_ACTIONS = frozenset(("open", "close", "minimize", "restore", "focus", "place"))
TARGET_MARKERS = {"es": {"open": "abre", "close": "cierra", "minimize": "minimiza",
                        "restore": "restaura", "focus": "enfoca", "place": "mueve"},
                  "en": {"open": "open", "close": "close", "minimize": "minimize",
                         "restore": "restore", "focus": "focus", "place": "move"}}


class ContextOrder(str):
    def __new__(cls, command, hypotheses=(), heard=""):
        obj = super().__new__(cls, command)
        obj.hypotheses = tuple(hypotheses)
        obj.heard = heard
        return obj


class ContextTitle(ContextOrder):
    pass


def contextual_score(query, label):
    q, label = simplify(query), simplify(label)
    base = phonetic_score(q, label)
    spoken, full = q.split(), label.split()
    if 1 < len(spoken) < len(full) and spoken[0] == full[0]:
        shortened = " ".join(full[:len(spoken)])
        base = max(base, phonetic_score(q, shortened) - 0.04)
    if min(len(q), len(label)) < 5:
        return base
    a, b = phonetic_key(q), phonetic_key(label)
    same_word = max((phonetic_score(left, right) for left in q.split() for right in label.split()), default=0)
    if same_word >= 0.9:
        base = max(base, 0.59 * base + 0.24)
    # Unstressed vowels vary substantially across languages. Require some
    # similarity before consulting the consonants; never promote to exact.
    consonants = lambda value: re.sub(r"[aeiou]", "", value)
    x, y = consonants(a), consonants(b)
    if min(len(x), len(y)) >= 3 and base >= 0.52:
        score = SequenceMatcher(None, x, y, autojunk=False).ratio()
        base = max(base, 0.65 * base + 0.35 * score)
    if len(spoken) >= 2 and len(full) >= 2 and base >= 0.51:
        pairs = zip(spoken[:len(full)], full)
        scores = [phonetic_score(left, right) for left, right in pairs]
        anchored = max(scores, default=0.0)
        if anchored >= 0.85:
            base = max(base, base * 0.78 + 0.22 * sum(scores) / len(scores))
    return base


def hypotheses(model, pcm, action, query, names, language="es"):
    """Rescore only shortlisted names made of words the acoustic model knows."""
    from vosk import KaldiRecognizer
    from wake_word import RATE, SAMPLE_BYTES

    if action not in TARGET_ACTIONS or not pcm:
        return ()
    marker = TARGET_MARKERS[language][action]
    if model.vosk_model_find_word(marker) < 0:
        return ()
    ranked = sorted(((contextual_score(query, name), name) for name in set(names)),
                    key=lambda item: (-item[0], item[1]))
    choices = {}
    for score, name in ranked[:32]:
        if score < 0.57:
            break
        phrase = " ".join(re.findall(r"[\w]+", name.lower()))
        if phrase and len(phrase.split()) <= 7 and all(model.vosk_model_find_word(word) >= 0
                                                       for word in phrase.split()):
            choices[f"{marker} {phrase}"] = name
    if not choices:
        return ()
    recognition = KaldiRecognizer(model, RATE, json.dumps([*choices, "[unk]"]))
    recognition.SetMaxAlternatives(3)
    completed = recognition.AcceptWaveform(pcm[:RATE * SAMPLE_BYTES * 6])
    result = recognition.Result() if completed else recognition.FinalResult()
    alternatives = json.loads(result).get("alternatives", [])
    return tuple(dict.fromkeys(choices[item["text"]] for item in alternatives
                               if item.get("text") in choices and item.get("confidence", 0) > 0))
