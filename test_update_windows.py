"""Exercise the packaged updater against real Windows executables."""
import base64
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import uuid4

from jarvis import Desktop
from updater import INSTALL, VERSION


@unittest.skipUnless(sys.platform == "win32", "Necesita el ejecutable de Windows")
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
        target = folder / f"JARVISUpdateProbe-{uuid4().hex}.exe"
        staged = folder / "new.jarvis-update"
        shutil.copy2("dist/JARVIS.exe", target)
        shutil.copy2("dist/JARVIS.exe", staged)
        receipt = folder / "initial.ready"
        old = subprocess.Popen([str(target)], env=dict(os.environ, JARVIS_UPDATE_RECEIPT=str(receipt)))
        helper = None
        desktop = Desktop()
        try:
            self.wait_until(receipt.exists)
            self.wait_until(lambda: any(exe == target.stem for _, _, exe in desktop.windows()))
            helper = self.helper(folder, target, staged, old.pid)
            time.sleep(1)
            self.assertIsNone(helper.poll())
            self.assertTrue(staged.exists())
            hwnd = next(hwnd for hwnd, _, exe in desktop.windows() if exe == target.stem)
            self.assertTrue(desktop.api.PostMessageW(hwnd, 0x0010, 0, 0))
            self.wait_until(lambda: not desktop.api.IsWindowVisible(hwnd))
            self.assertIsNone(old.poll(), "Cerrar la ventana debe dejar JARVIS activo.")
            self.assertIsNone(helper.poll(), "El actualizador debe seguir esperando al proceso.")
            duplicate = subprocess.Popen([str(target)])
            try:
                self.assertEqual(duplicate.wait(timeout=30), 0)
                self.wait_until(lambda: any(exe == target.stem for _, _, exe in desktop.windows()))
            finally:
                if duplicate.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(duplicate.pid), "/T", "/F"], capture_output=True)
            # Explicit quitting is covered by the resident test. Stop this fixture
            # so the real updater can replace the locked executable.
            subprocess.run(["taskkill", "/PID", str(old.pid), "/T", "/F"], capture_output=True, check=True)
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
            subprocess.run(["taskkill", "/IM", target.name, "/T", "/F"], capture_output=True)
            old.wait(timeout=30)
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
        log = (folder / "JARVIS/actualizacion.log").read_text(encoding="utf-8-sig")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), previous_hash, log)
        self.assertIn("Abrir la nueva versión", log)
        self.assertIn(str(target), log)


if __name__ == "__main__":
    unittest.main()
