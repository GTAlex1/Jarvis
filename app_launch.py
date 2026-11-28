"""Verify application activation using newly observed desktop evidence."""
from dataclasses import dataclass
from pathlib import PureWindowsPath
import re
from time import monotonic, sleep



@dataclass(frozen=True)
class Running:
    pid: int
    executable: str
    aumid: str = ""
    window: int = 0
    started: int = 0


def matches_identity(app, running):
    path = PureWindowsPath(running.executable)
    appid = running.aumid.casefold()
    webapps = [identity.value for identity in app.evidence if identity.kind == "webapp"]
    if webapps:
        ids = [identity.value.casefold() for identity in app.evidence if identity.kind == "aumid"]
        if ids:
            return bool(running.window and appid in ids)
        return bool(running.window and any(
            re.search(r"(?:^|[._])" + re.escape(webapp) + r"(?:$|[._ ])", appid) for webapp in webapps
        ))
    name = path.name.casefold()
    if app.game:
        from game_providers import LAUNCHERS
        if (path.stem.casefold() in LAUNCHERS or name.startswith(("crash", "unins", "install"))
                or re.search(r"launcher|bootstrap|anticheat|redist|setup|helper|overlay|update", name)):
            return False
    roots = tuple(PureWindowsPath(identity.value) for identity in app.evidence
                  if identity.kind == "game_root")
    for identity in app.evidence:
        if identity.kind == "aumid" and running.aumid.casefold() == identity.value.casefold():
            return True
        if identity.kind == "exe" and path == PureWindowsPath(identity.value):
            return True
        if identity.kind == "game_image" and name == identity.value.casefold():
            if not roots or any(root in path.parents for root in roots):
                return True
    # An unknown executable is only evidence with a visible window in a
    # launcher-reported installation directory, never by directory alone.
    return bool(name and running.window and not any(i.kind == "game_image" for i in app.evidence)
                and any(root in path.parents for root in roots))


@dataclass(frozen=True)
class LaunchResult:
    state: str
    message: str


def launch_verified(app, observe, launch, timeout=None, clock=monotonic, pause=sleep):
    if app.route.kind == "unavailable":
        return LaunchResult("unavailable", f"Encontré «{app.name}», pero no hay una ruta de arranque disponible. {app.note}".strip())
    before = {instance for instance in observe() if matches_identity(app, instance)}
    launch(app)
    limit = timeout if timeout is not None else (8 if app.game else 2)
    deadline = clock() + (min(0.75, limit) if before else limit)
    after = set()
    while True:
        after = {instance for instance in observe() if matches_identity(app, instance)}
        if after - before:
            return LaunchResult("verified", f"Comprobé que se abrió «{app.name}».")
        remaining = deadline - clock()
        if remaining <= 0:
            break
        pause(min(0.4, remaining))
    if before & after:
        return LaunchResult("already_running", f"«{app.name}» ya estaba abierto. Envié la solicitud a Windows.")
    detail = f" {app.note}" if app.note else ""
    return LaunchResult("unverified", f"Solicité abrir «{app.name}», pero no pude comprobar su arranque.{detail}")


@dataclass
class PendingLaunch:
    app: object
    before: frozenset
    deadline: float
    phase: str = "requested"
    extended: bool = False


def launch_progress(app, before, instances, deadline, now):
    """Describe evidence from the product separately from its launcher."""
    from game_providers import LAUNCHERS

    matching = {instance for instance in instances if matches_identity(app, instance)}
    fresh = matching - before
    if any(not app.game or entry.window for entry in fresh):
        noun = "El juego" if app.game else "La aplicación"
        return LaunchResult("verified", f"{noun} «{app.name}» está en ejecución.")
    if before & matching:
        return LaunchResult("already_running", f"«{app.name}» ya estaba abierto antes de la solicitud.")
    if now >= deadline:
        if app.note:
            return LaunchResult("manual", f"No confirmé el arranque de «{app.name}». {app.note}")
        return LaunchResult("unverified", f"Se agotó el plazo sin confirmar el arranque de «{app.name}».")
    if fresh:
        return LaunchResult("starting", f"El proceso de «{app.name}» ha arrancado. Espero su ventana.")
    if app.game and any(LAUNCHERS.get(PureWindowsPath(item.executable).stem.casefold()) == app.source
                        for item in instances):
        return LaunchResult("launcher", f"El cliente de «{app.name}» está abierto. El juego aún no está confirmado.")
    return LaunchResult("requested", "")


class LaunchMonitor:
    """One polling worker handles concurrent launch checks without holding the command queue."""
    def __init__(self, observe, launch, on_result, clock=monotonic):
        from threading import Condition, Thread
        self.observe, self.launch, self.on_result, self.clock = observe, launch, on_result, clock
        self.condition = Condition()
        self.pending = {}
        self.closed = False
        self.worker = Thread(target=self.run, name="jarvis-launch-check", daemon=True)
        self.worker.start()

    def submit(self, app):
        if app.route.kind == "unavailable":
            return launch_verified(app, self.observe, self.launch).message
        try:
            before = frozenset(item for item in self.observe() if matches_identity(app, item)
                               and (not app.game or item.window))
        except OSError:
            # Verification is best effort. With no baseline, don't claim a new launch.
            self.launch(app)
            return f"Solicité abrir «{app.name}». Windows impidió comprobar el estado anterior."
        with self.condition:
            if app.key in self.pending:
                return f"Ya estoy comprobando el arranque de «{app.name}»."
            if len(self.pending) >= 16:
                return "Hay demasiados arranques comprobándose. Espera unos segundos y vuelve a intentarlo."
            self.launch(app)
            self.pending[app.key] = PendingLaunch(app, before, self.clock() + (45 if app.game else 8))
            self.condition.notify()
        if app.game and app.note:
            return f"Solicité abrir «{app.name}». {app.note} Comprobaré el arranque en segundo plano."
        return f"Solicité abrir «{app.name}». Comprobaré el arranque en segundo plano."

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.pending)
                if self.closed:
                    return
                batch = tuple(self.pending.items())
            now = self.clock()
            try:
                instances = tuple(self.observe())
            except OSError:
                instances = ()
            for key, job in batch:
                result = launch_progress(job.app, job.before, instances, job.deadline, now)
                if result.state == "starting" and not job.extended:
                    job.extended = True
                    job.deadline = max(job.deadline, now + 30)
                done = result.state in {"verified", "already_running", "manual", "unverified"}
                with self.condition:
                    if self.closed:
                        return
                    if done:
                        self.pending.pop(key, None)
                if result.message and (done or job.phase != result.state):
                    job.phase = result.state
                    self.on_result(result)
            with self.condition:
                if not self.closed and self.pending:
                    self.condition.wait(timeout=1.0)

    def close(self):
        with self.condition:
            self.closed = True
            self.pending.clear()
            self.condition.notify_all()
        self.worker.join(timeout=3)
