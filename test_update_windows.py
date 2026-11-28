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

    def helper(self, folder, target, staged, pid, script=INSTALL, expected=None):
        env = dict(os.environ, LOCALAPPDATA=str(folder),
                   JARVIS_UPDATE_TARGET=str(target), JARVIS_UPDATE_STAGED=str(staged),
                   JARVIS_UPDATE_PID=str(pid), JARVIS_UPDATE_TEST="1")
        if expected:
            env["JARVIS_UPDATE_EXPECTED"] = expected
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        return subprocess.Popen(
            [str(powershell), "-NoProfile", "-STA", "-EncodedCommand",
             base64.b64encode(script.encode("utf-16le")).decode("ascii")],
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

    @unittest.skipUnless(os.getenv("JARVIS_TEST_LEGACY_EXE"), "Requiere el ejecutable publicado de 0.4.1")
    def test_direct_upgrade_with_the_0_4_1_updater(self):
        self.exercise_direct_upgrade("JARVIS_TEST_LEGACY_EXE", "0.4.1",
                                     "59ffff20d6d47348cba9941b4930fb10e177a553605fd15c749722d1dc1e148d",
                                     closes_with_window=True)

    @unittest.skipUnless(os.getenv("JARVIS_TEST_PREVIOUS_EXE"), "Requiere el ejecutable publicado de 0.6.4")
    def test_compatible_replacement_from_0_6_4(self):
        self.exercise_direct_upgrade("JARVIS_TEST_PREVIOUS_EXE", "0.6.4",
                                     "eff32df9466a49bc8ce72cdba542d07dcc97e2859e010876ea60fbee093257a4")

    def exercise_direct_upgrade(self, env, version, digest, closes_with_window=False):
        old_exe = Path(os.environ[env])
        self.assertEqual(hashlib.sha256(old_exe.read_bytes()).hexdigest(), digest)
        legacy = {}
        old_source = subprocess.check_output(["git", "show", f"v{version}:updater.py"])
        exec(compile(old_source, f"updater-{version}.py", "exec"), legacy)
        self.assertLessEqual(Path("dist/JARVIS.exe").stat().st_size, legacy["MAX_SIZE"])

        folder = Path(tempfile.mkdtemp(prefix="JARVIS actualización directa "))
        target = folder / f"JARVISLegacyProbe-{uuid4().hex}.exe"
        staged = folder / "new.jarvis-update"
        receipt = folder / "legacy.ready"
        shutil.copy2(old_exe, target)
        shutil.copy2("dist/JARVIS.exe", staged)
        desktop = Desktop()
        old = subprocess.Popen([str(target)], env=dict(os.environ, JARVIS_UPDATE_RECEIPT=str(receipt)))
        helper = None
        try:
            self.wait_until(lambda: receipt.exists() and receipt.read_text(encoding="utf-8") == version)
            self.wait_until(lambda: any(exe == target.stem for _, _, exe in desktop.windows()))
            helper = self.helper(folder, target, staged, old.pid, legacy["INSTALL"])
            if closes_with_window:
                hwnd = next(hwnd for hwnd, _, exe in desktop.windows() if exe == target.stem)
                self.assertTrue(desktop.api.PostMessageW(hwnd, 0x0010, 0, 0))
            else:
                subprocess.run(["taskkill", "/PID", str(old.pid), "/T", "/F"], capture_output=True, check=True)
            old.wait(timeout=30)
            _, stderr = helper.communicate(timeout=100)
            self.assertEqual(helper.returncode, 0, stderr.decode("utf-8", errors="replace"))
            log = (folder / "JARVIS/actualizacion.log").read_text(encoding="utf-8-sig")
            self.assertIn("Actualización correcta a " + VERSION, log)
            self.assertTrue(any(exe == target.stem for _, _, exe in desktop.windows()))
        finally:
            if helper and helper.poll() is None:
                helper.kill()
                helper.communicate()
            subprocess.run(["taskkill", "/IM", target.name, "/T", "/F"], capture_output=True)
            old.wait(timeout=30)

    @unittest.skipUnless(os.getenv("JARVIS_TEST_BRIDGE_EXE"), "Requiere el binario 0.6.4.1")
    def test_automatic_update_from_0_6_4_1_uses_compatible_asset(self):
        self.exercise_direct_upgrade("JARVIS_TEST_BRIDGE_EXE", "0.6.4.1",
                                     "7ca1421c7b72b131779e08883d65e410b30b5ff46699bf5bde914e2498503826")

    @unittest.skipUnless(os.getenv("JARVIS_TEST_CATALOG_PREVIOUS_EXE"), "Requiere el binario 0.6.4.2")
    def test_direct_upgrade_from_0_6_4_2(self):
        self.exercise_direct_upgrade("JARVIS_TEST_CATALOG_PREVIOUS_EXE", "0.6.4.2",
                                     "a34a5a35784281db6eba6f0f094eca1333f59603c300f2755dfe0a30f682ef92")

    def test_rollback_of_started_binary_with_wrong_version_receipt(self):
        folder = Path(tempfile.mkdtemp(prefix="JARVIS rollback versión "))
        target = folder / f"JARVISReceiptProbe-{uuid4().hex}.exe"
        staged = folder / "wrong.jarvis-update"
        original = b"original preserved"
        target.write_bytes(original)
        shutil.copy2("dist/JARVIS.exe", staged)
        helper = self.helper(folder, target, staged, 2147483647, expected="9.0.0")
        try:
            _, error = helper.communicate(timeout=100)
            self.assertEqual(helper.returncode, 1, error.decode("utf-8", errors="replace"))
            self.assertEqual(target.read_bytes(), original)
            self.assertIn("no confirmó la versión", (folder / "JARVIS/actualizacion.log").read_text(encoding="utf-8-sig"))
        finally:
            if helper.poll() is None:
                helper.kill()
                helper.communicate()
            subprocess.run(["taskkill", "/IM", target.name, "/T", "/F"], capture_output=True)

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
