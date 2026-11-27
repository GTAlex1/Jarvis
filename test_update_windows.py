"""Exercise the packaged updater against real Windows executables."""
import base64
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from jarvis import Desktop
from updater import INSTALL, VERSION


class PackagedUpdateTest(unittest.TestCase):
    def wait_until(self, predicate, timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.2)
        self.fail("No se completó la condición de actualización a tiempo.")

    def helper(self, folder, target, staged, pid):
        env = dict(os.environ, LOCALAPPDATA=str(folder),
                   JARVIS_UPDATE_TARGET=str(target), JARVIS_UPDATE_STAGED=str(staged),
                   JARVIS_UPDATE_PID=str(pid), JARVIS_UPDATE_TEST="1")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        return subprocess.Popen(
            [str(powershell), "-NoProfile", "-STA", "-EncodedCommand",
             base64.b64encode(INSTALL.encode("utf-16le")).decode("ascii")],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_real_executable_replaced_and_reopened(self):
        folder = Path(tempfile.mkdtemp(prefix="JARVIS actualización con espacios "))
        target = folder / "JARVISUpdateProbe.exe"
        staged = folder / "new.jarvis-update"
        shutil.copy2("dist/JARVIS.exe", target)
        shutil.copy2("dist/JARVIS.exe", staged)
        receipt = folder / "initial.ready"
        old = subprocess.Popen([str(target)], env=dict(os.environ, JARVIS_UPDATE_RECEIPT=str(receipt)))
        helper = None
        desktop = Desktop()
        try:
            self.wait_until(receipt.exists)
            helper = self.helper(folder, target, staged, old.pid)
            time.sleep(1)
            self.assertIsNone(helper.poll())
            self.assertTrue(staged.exists())
            for hwnd, _, executable in desktop.windows():
                if executable == target.stem:
                    desktop.api.PostMessageW(hwnd, 0x0010, 0, 0)
            old.wait(timeout=30)
            out, err = helper.communicate(timeout=100)
            self.assertEqual(helper.returncode, 0, err.decode("utf-8", errors="replace"))
            self.assertIn("Actualización correcta a " + VERSION,
                          (folder / "JARVIS/actualizacion.log").read_text(encoding="utf-8-sig"))
            self.assertFalse(staged.exists())
            self.assertFalse(Path(str(staged) + ".backup").exists())
            self.assertTrue(any(exe == target.stem for _, _, exe in desktop.windows()))
        finally:
            if helper and helper.poll() is None:
                helper.kill()
                helper.communicate()
            for hwnd, _, executable in desktop.windows():
                if executable == target.stem:
                    desktop.api.PostMessageW(hwnd, 0x0010, 0, 0)
            if old.poll() is None:
                subprocess.run(["taskkill", "/PID", str(old.pid), "/T", "/F"], capture_output=True)
            # The test directory is temporary and the CI runner removes it.

    def test_failed_start_restores_old_file_and_logs_error(self):
        folder = Path(tempfile.mkdtemp(prefix="JARVIS rollback "))
        target = folder / "previous.exe"
        staged = folder / "broken.jarvis-update"
        shutil.copy2("dist/JARVIS.exe", target)
        previous_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        staged.write_bytes(b"invalid executable")
        helper = self.helper(folder, target, staged, 2147483647)
        out, err = helper.communicate(timeout=100)
        self.assertEqual(helper.returncode, 1)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), previous_hash)
        log = (folder / "JARVIS/actualizacion.log").read_text(encoding="utf-8-sig")
        self.assertIn("Abrir la nueva versión", log)
        self.assertIn(str(target), log)


if __name__ == "__main__":
    unittest.main()
