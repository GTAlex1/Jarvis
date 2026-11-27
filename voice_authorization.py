"""Single-use session-bound approvals, independent of desktop UI."""
from dataclasses import dataclass
from hmac import compare_digest
from secrets import randbelow, token_urlsafe

from permissions import CODE

UNVERIFIED = "<biometrics-disabled>"


@dataclass(frozen=True)
class LocalApproval:
    command: object
    description: str
    method: str = CODE
    category: str = "close"
    ticket: str = ""


@dataclass(frozen=True)
class ApprovalAnswer:
    ticket: str
    yes: bool


@dataclass(frozen=True)
class PowerAction:
    operation: str


@dataclass(frozen=True)
class PendingApproval:
    request: LocalApproval
    speaker: str
    code: str
    expires: float
    ticket: str
    revision: int = 0

    @classmethod
    def create(cls, request, speaker, now, revision=0):
        code = f"{randbelow(1000000):06d}" if request.method == CODE else ""
        return cls(request, speaker, code, now + 25, token_urlsafe(16), revision)

    def valid(self, now, profiles, revision=None):
        return (now < self.expires and (revision is None or revision == self.revision)
                and (self.speaker == UNVERIFIED or any(profile.id == self.speaker for profile in profiles)))

    def matches(self, method, ticket, code=""):
        return (self.request.method == method and self.ticket == ticket and
                (method != CODE or isinstance(code, str) and
                 compare_digest(self.code.encode("ascii"), code.encode("utf-8"))))



@dataclass(frozen=True)
class PowerScheduled:
    message: str


@dataclass(frozen=True)
class RejectedAction:
    message: str
    reason: str


@dataclass(frozen=True)
class ExitAction:
    pass
