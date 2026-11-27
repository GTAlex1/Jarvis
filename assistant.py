"""Command execution shared by desktop frontends and future input sources."""
from concurrent.futures import ThreadPoolExecutor

from dialogue import SelectedCommand
from jarvis import Desktop, execute
from voice_authorization import RejectedAction


class Assistant:
    def __init__(self):
        # Set process DPI awareness before the desktop frontend creates windows.
        self.desktop = Desktop()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-command")

    def submit(self, command):
        return self.worker.submit(self.execute, command)

    def submit_voice(self, command, approved=False, guard=None, policy=None):
        return self.worker.submit(self.execute, command, conversational=True, guard=guard,
                                  policy=policy, approved=approved)

    def execute(self, command, conversational=False, guard=None, policy=None, approved=False):
        if guard is not None and not guard():
            return "Se canceló la acción de voz."
        selection = None
        if isinstance(command, SelectedCommand):
            selection = command.option.target
            command = command.command
        try:
            return execute(self.desktop, command, conversational, selection, policy=policy, approved=approved)
        except OSError as error:
            message = f"No se pudo completar la orden: {error}"
            return RejectedAction(message, "windows") if policy is not None else message

    def close(self):
        self.worker.shutdown(cancel_futures=True)
