"""Native Windows adapter for power actions."""
import os
from pathlib import Path
import subprocess


def perform_power(operation):
    switch = {"shutdown": "/s", "restart": "/r"}[operation]
    executable = Path(os.environ["SystemRoot"]) / "System32" / "shutdown.exe"
    # Windows implies /f when /t is positive. The UI owns the countdown.
    subprocess.run([str(executable), switch, "/t", "0"], check=True, timeout=5,
                   creationflags=subprocess.CREATE_NO_WINDOW)
