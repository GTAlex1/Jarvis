"""Local application identities, matching, and asynchronous discovery."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path, PureWindowsPath
import re
from threading import Lock
from time import time

from command_language import phonetic_score, simplify
from voice_context import contextual_score


@dataclass(frozen=True)
class Identity:
    kind: str
    value: str


@dataclass(frozen=True)
class Application:
    name: str
    source: str
    route: Identity
    evidence: tuple = ()
    aliases: tuple = ()
    game: bool = False
    note: str = ""
    backing: str = ""

    @property
    def key(self):
        return self.route.kind, self.route.value.casefold()


def name_key(value):
    return " ".join(re.findall(r"[^\W_]+", simplify(value), re.UNICODE))


def labels(app):
    return (app.name, *app.aliases, *(PureWindowsPath(i.value).stem for i in app.evidence
                                      if i.kind == "exe" and not app.game))


def resolve(query, items, names):
    """Return possible targets and whether the user must confirm a fuzzy match."""
    hints = tuple(map(name_key, getattr(query, "hypotheses", ())))
    contextual = hasattr(query, "hypotheses")
    query = name_key(query)
    if not query:
        return (), False
    candidates = [(item, tuple(filter(None, map(name_key, names(item))))) for item in items]
    exact = tuple(item for item, keys in candidates if query in keys)
    if exact:
        return exact, False
    # Prefixes, acronyms and text/phonetic errors all need confirmation.
    if len(query.replace(" ", "")) < 3:
        return (), False
    ranked = []
    for item, keys in candidates:
        score = max((max((contextual_score if contextual else phonetic_score)(query, key), 0.88 if (
            key.startswith(query) or query == "".join(word[0] for word in key.split())
        ) else 0) for key in keys), default=0)
        if score >= 0.57 and any(hint in keys for hint in hints):
            score = max(score, 0.87)
        if score >= (0.64 if contextual else 0.70):
            ranked.append((score, item))
    ranked.sort(key=lambda entry: -entry[0])
    return tuple(item for score, item in ranked[:5] if score >= ranked[0][0] - (0.17 if contextual else 0.13)), bool(ranked)


def consolidate(applications):
    """Merge duplicate routes, then merge lower quality entries by verified identity."""
    result = []
    routes = {}
    executable_indices = {}
    appids = {}
    sources = {"steam": 0, "epic": 0, "riot": 0, "hoyoplay": 0, "xbox": 0, "ea": 0,
               "ubisoft": 0, "battlenet": 0, "gog": 0, "start": 1, "shortcut": 2,
               "registry": 3, "portable": 4}
    for app in sorted(applications, key=lambda app: sources.get(app.source, 2)):
        index = routes.get(app.key)
        if index is None and not app.game:
            for identity in app.evidence:
                if identity.kind == "aumid" and identity.value.casefold() in appids:
                    index = appids[identity.value.casefold()]
                    break
        if index is None and not app.game and app.route.kind != "appsfolder":
            keys = {i.value.casefold() for i in app.evidence if i.kind == "exe"}
            for key in keys:
                compatible = executable_indices.get(key, ())
                if app.source == "shortcut":
                    compatible = [candidate for candidate in compatible
                                  if result[candidate].source == "start"
                                  and name_key(app.name) == name_key(result[candidate].name)]
                if len(compatible) == 1:
                    index = next(iter(compatible))
                    break
        if index is None:
            index = len(result)
            result.append(app)
        else:
            preferred = result[index]
            if preferred.game and not app.game:
                continue
            result[index] = Application(preferred.name, preferred.source, preferred.route,
                                        tuple(dict.fromkeys((*preferred.evidence, *app.evidence))),
                                        tuple(dict.fromkeys((*preferred.aliases, app.name, *app.aliases))),
                                        preferred.game, preferred.note, preferred.backing)
        routes[app.key] = index
        if not app.game:
            for identity in app.evidence:
                if identity.kind == "aumid":
                    appids[identity.value.casefold()] = index
                if identity.kind == "exe":
                    executable_indices.setdefault(identity.value.casefold(), set()).add(index)
    return tuple(sorted(result, key=lambda app: (name_key(app.name), app.key)))


@dataclass(frozen=True)
class Discovery:
    entries: tuple
    failed: frozenset = frozenset()


def collect_source(name, collect, failed, affected=()):
    """Keep a broken provider from hiding all the other applications."""
    try:
        return tuple(collect())
    except Exception:
        failed.update(affected or (name,))
        logging.getLogger(__name__).exception("Falló la fuente del catálogo %s", name)
        return ()


class Catalog:
    schema = 1

    def __init__(self, path, providers, valid, ttl=1800):
        self.path = Path(path)
        self.providers = providers
        self.valid = valid
        self.ttl = ttl
        self.lock = Lock()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-catalog")
        self.future = None
        self.changed = False
        self.entries, self.updated = self._read()

    def _read(self):
        try:
            with self.path.open(encoding="utf-8") as stream:
                if self.path.stat().st_size > 8_000_000:
                    return (), 0
                record = json.load(stream)
            if record["schema"] != self.schema:
                return (), 0
            entries = tuple(Application(**{
                **item, "route": Identity(**item["route"]),
                "evidence": tuple(Identity(**identity) for identity in item["evidence"]),
                "aliases": tuple(item["aliases"]),
            }) for item in record["entries"])
            if not all(isinstance(app.name, str) and isinstance(app.route.value, str)
                       and all(isinstance(alias, str) for alias in app.aliases) for app in entries):
                return (), 0
            return entries, min(float(record["updated"]), time())
        except (AttributeError, OSError, TypeError, ValueError, KeyError):
            return (), 0

    def refresh(self, force=False):
        with self.lock:
            if self.future and not self.future.done():
                self.changed |= force
                return self.future
            if force or time() - self.updated >= self.ttl:
                self.future = self.worker.submit(self._refresh)
            return self.future

    def _refresh(self):
        while True:
            discovered = []
            failures = set()
            for name, provider in self.providers:
                try:
                    result = provider()
                    if isinstance(result, Discovery):
                        failures.update(result.failed)
                        discovered.extend(result.entries)
                    else:
                        discovered.extend(tuple(result))
                except Exception:
                    failures.add(name)
                    logging.getLogger(__name__).exception("Falló el catálogo %s", name)
            with self.lock:
                preserved = [app for app in self.entries if ("windows" in failures or app.source in failures) and self.valid(app)]
                self.entries = consolidate((*discovered, *preserved))
                self.updated = time()
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temp = self.path.with_suffix(".tmp")
                    temp.write_text(json.dumps({"schema": self.schema, "updated": self.updated,
                                                "entries": [asdict(app) for app in self.entries]},
                                               ensure_ascii=False), encoding="utf-8")
                    temp.replace(self.path)
                except OSError:
                    pass
                if not self.changed:
                    return
                self.changed = False

    def snapshot(self, wait=False):
        future = self.refresh()
        if future and wait and not self.entries:
            future.result()
        return self.entries

    def close(self):
        self.worker.shutdown(cancel_futures=True)
