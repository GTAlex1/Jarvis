import sys
import unittest
from unittest.mock import Mock, patch

from preferences import startup_command


class StartupCommandTest(unittest.TestCase):
    def test_quotes_both_installation_modes(self):
        self.assertEqual(startup_command(r"C:\Soy Alex\JARVIS.exe"),
                         r'"C:\Soy Alex\JARVIS.exe" --background')
        self.assertEqual(
            startup_command(r"C:\Mi Python\pythonw.exe", r"C:\Mi Jarvis\jarvis_gui.py"),
            r'"C:\Mi Python\pythonw.exe" "C:\Mi Jarvis\jarvis_gui.py" --background',
        )

    def test_rejects_paths_over_windows_limit(self):
        with self.assertRaises(ValueError):
            startup_command("C:\\" + "あ" * 235, "jarvis_gui.py")


@unittest.skipUnless(sys.platform == "win32", "Necesita la bandeja de Windows")
class ResidentTest(unittest.TestCase):
    def is_animated(self, root):
        callbacks = root.tk.splitlist(root.tk.call("after", "info"))
        return any("animate" in root.tk.call("after", "info", timer)[0] for timer in callbacks)

    def test_native_tray_reopens_the_only_instance(self):
        import tkinter as tk

        from jarvis_gui import create_panel
        from resident import Resident
        from windows_tray import show_running_instance, single_instance

        with single_instance() as first:
            self.assertTrue(first)
            with single_instance() as duplicate:
                self.assertFalse(duplicate)

            root = tk.Tk()
            root.withdraw()
            with (patch("resident.microphone_enabled", return_value=True),
                  patch("resident.starts_with_windows", return_value=False),
                  patch("resident.set_microphone") as microphone,
                  patch("resident.set_startup") as startup):
                resident = Resident(root, Mock(), create_panel)
                try:
                    self.assertTrue(resident.tray.add_icon(), "No se pudo registrar el icono en Explorer.")
                    self.assertIsNone(resident.panel)
                    self.assertEqual(root.state(), "withdrawn")
                    self.assertTrue(show_running_instance())
                    root.update()
                    resident.deliver()
                    root.update()
                    self.assertEqual(root.state(), "normal")
                    self.assertIsNotNone(resident.panel)
                    panel = resident.panel
                    self.assertTrue(self.is_animated(root))

                    # Invoke the same window protocol triggered by clicking X.
                    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    root.update()
                    self.assertEqual(root.state(), "withdrawn")
                    self.assertFalse(self.is_animated(root))
                    self.assertTrue(show_running_instance())
                    root.update()
                    resident.deliver()
                    root.update()
                    self.assertIs(resident.panel, panel)
                    self.assertEqual(root.state(), "normal")

                    for index, setting, enabled in ((1, microphone, False), (2, startup, True)):
                        _, _, action = resident.menu_items()[index]
                        resident.run_action(action)
                        setting.assert_called_once_with(enabled)
                        self.assertEqual(resident.menu_items()[index][1], enabled)

                    self.assertFalse(resident.submit("Jarvis, salir"))
                    self.assertTrue(resident.closing)
                finally:
                    resident.tray.close()
                    root.destroy()

            with single_instance() as duplicate:
                self.assertFalse(duplicate)
        with single_instance() as first:
            self.assertTrue(first)


class ResidentLogicTest(unittest.TestCase):
    def test_successful_update_uses_complete_shutdown(self):
        from resident import Resident

        resident = Resident.__new__(Resident)
        resident.root = Mock()
        resident.installing = resident.update_busy = True
        resident.finish_update(None, None)
        resident.root.quit.assert_called_once_with()
        self.assertTrue(resident.closing)
