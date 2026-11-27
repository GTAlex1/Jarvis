"""Command execution shared by desktop frontends and future input sources."""
from concurrent.futures import ThreadPoolExecutor

from dialogue import SelectedCommand
from jarvis import Desktop, execute


class Assistant:
    def __init__(self):
        # Set process DPI awareness before the desktop frontend creates windows.
        self.desktop = Desktop()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-command")

    def submit(self, command):
        return self.worker.submit(self.execute, command)

    def submit_voice(self, command):
        return self.worker.submit(self.execute, command, conversational=True)

    def execute(self, command, conversational=False):
        selection = None
        if isinstance(command, SelectedCommand):
            selection = command.option.target
            command = command.command
        try:
            return execute(self.desktop, command, conversational, selection)
        except OSError as error:
            return f"No se pudo completar la orden: {error}"

    def close(self):
        self.worker.shutdown(cancel_futures=True)
