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
