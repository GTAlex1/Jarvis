"""Bounded local approval requests for voice-initiated desktop actions."""
from dataclasses import dataclass
from secrets import randbelow


@dataclass(frozen=True)
class LocalApproval:
    command: object
    description: str


@dataclass(frozen=True)
class PendingApproval:
    request: LocalApproval
    speaker: str
    code: str
    expires: float

    @classmethod
    def create(cls, request, speaker, now):
        return cls(request, speaker, f"{randbelow(1000000):06d}", now + 25)

    def valid(self, now, profiles):
        return now < self.expires and any(profile.id == self.speaker for profile in profiles)


def sensitive_intent(intent, selected_label=""):
    administration = {"administrador de tareas", "task manager", "configuracion", "settings", "ajustes", "windows update"}
    return (intent[0] in {"close", "exit"} or
            intent == ("system", "lock") or intent == ("system", "screenshot") or
            (intent[0] == "open" and (intent[1] in administration or selected_label in administration)))
