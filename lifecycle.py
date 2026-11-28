"""Graceful game and launcher shutdown with explicit evidence for dependencies."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PureWindowsPath
from threading import Event, Lock
from time import monotonic

from app_catalog import name_key
from app_launch import matches_identity


@dataclass(frozen=True)
class LifecycleSettings:
    enabled: bool = False
    providers: tuple = ()
    games: tuple = ()

    def allows(self, game, requested=False):
        return ((self.enabled or requested) and game.source not in self.providers
                and name_key(game.name) not in self.games)


def product_owner(instance, catalog):
    matches = [app for app in catalog if app.game and matches_identity(app, instance)]
    return matches[0] if len(matches) == 1 else None


def associated_launchers(game, instances, catalog):
    from game_providers import LAUNCHERS
    # Require both a provider and the exact path of a local launcher registered
    # by Windows. Process names alone never authorize a second close.
    paths = {PureWindowsPath(e.value) for app in catalog if not app.game for e in app.evidence
             if e.kind == "exe" and LAUNCHERS.get(PureWindowsPath(e.value).stem.casefold()) == game.source}
    return {instance for instance in instances if instance.window and instance.started
            and PureWindowsPath(instance.executable) in paths}


def close_verdict(game, instances, catalog, candidate, provider_state, pending_launch):
    if pending_launch or any(matches_identity(game, item) for item in instances):
        return "active"
    if any(app.game and app != game and app.source == game.source and matches_identity(app, item)
           for app in catalog for item in instances):
        return "dependent"
    if candidate not in associated_launchers(game, instances, catalog):
        return "unknown"
    state = provider_state(game.source, candidate)
    return state if state in {"idle", "busy"} else "unknown"


def provider_activity(provider, launcher):
    # The current clients expose launch routes but no validated read-only
    # proof that this session has no download, update or install. An empty
    # process list, an old log or a quiet network is not positive proof.
    return "unknown"


class LifecycleMonitor:
    def __init__(self, observe, close_window, report, pending_launch, activity=provider_activity):
        self.observe, self.close_window, self.report = observe, close_window, report
        self.pending_launch, self.activity = pending_launch, activity
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-lifecycle")
        self.stopping = Event()
        self.lock = Lock()
        self.pending = set()

    def submit(self, game, owner, catalog, close_launcher, guard=None):
        # The initial WM_CLOSE is sent through the normal command path.
        with self.lock:
            if len(self.pending) >= 6 or game.key in self.pending:
                return False
            self.pending.add(game.key)
        self.worker.submit(self._track, game, owner, tuple(catalog), close_launcher, guard)
        return True

    def _track(self, game, owner, catalog, close_launcher, guard):
        try:
            self.track(game, owner, catalog, close_launcher, guard)
        except OSError:
            self.report(f"Windows impidió verificar el cierre de «{game.name}».")
        finally:
            with self.lock:
                self.pending.discard(game.key)

    def track(self, game, owner, catalog, close_launcher, guard, clock=monotonic, wait=None):
        wait = self.stopping.wait if wait is None else wait
        deadline = clock() + 22
        while not self.stopping.is_set():
            instances = tuple(self.observe())
            if not any((item.pid, item.started) == (owner.pid, owner.started) or matches_identity(game, item)
                       for item in instances):
                break
            if clock() >= deadline:
                self.report(f"«{game.name}» sigue en ejecución. Comprueba si pide confirmar el cierre.")
                return
            if wait(0.75):
                return
        if self.stopping.is_set():
            return
        self.report(f"Comprobé que «{game.name}» terminó.")
        if not close_launcher:
            return

        deadline = clock() + 9
        while not self.stopping.is_set():
            instances = tuple(self.observe())
            launchers = associated_launchers(game, instances, catalog)
            if launchers or clock() >= deadline:
                break
            if wait(0.75):
                return
        if not launchers or self.stopping.is_set():
            return
        if len(launchers) != 1:
            self.report("Dejé los launchers abiertos porque hay más de una sesión posible.")
            return
        candidate, = launchers
        verdict = close_verdict(game, tuple(self.observe()), catalog, candidate, self.activity, self.pending_launch())
        if verdict != "idle" or (guard and not guard()):
            reasons = {"active": "hay un juego arrancando o activo", "dependent": "hay otro juego activo",
                       "busy": "hay una tarea del cliente en curso", "unknown": "no pude verificar descargas o instalaciones"}
            self.report(f"Dejé el launcher de «{game.name}» abierto: {reasons.get(verdict, 'la autorización ya no está activa')}.")
            return
        if not self.close_window(candidate):
            self.report("El launcher cambió o Windows rechazó el cierre.")
            return
        deadline = clock() + 5
        while clock() < deadline:
            if not any(item.window == candidate.window and item.pid == candidate.pid for item in self.observe()):
                self.report(f"La ventana del launcher de «{game.name}» se cerró.")
                return
            if wait(0.5):
                return
        self.report(f"El launcher de «{game.name}» sigue visible tras solicitar el cierre.")

    def close(self):
        self.stopping.set()
        self.worker.shutdown(cancel_futures=True)
