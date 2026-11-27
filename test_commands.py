import ctypes as c
from ctypes import wintypes as w
import sys
import unittest
from unittest.mock import patch, Mock
from commands import parse, rectangle
from jarvis import Desktop, execute, matching_windows


class CommandsTest(unittest.TestCase):
    def test_user_phrases_and_previous_syntax(self):
        cases = {
            "VSCode izquieda": ("place", "vscode", "left", None),
            "Visual Studio Code pantalla completa": ("place", "visual studio code", "full", None),
            "Mueve la pestaña VSCode a la mitad izquierda de la pantalla 1": ("place", "vscode", "left", 1),
            "pon la ventana de Firefox a la mitad derecha del monitor 2": ("place", "firefox", "right", 2),
            "mueve VSCode a la pantalla 2": ("place", "vscode", "monitor", 2),
            "Chrome esquina superior izquierda monitor 2": ("place", "chrome", "top_left", 2),
            "pon Chrome en la esquina superior derecha": ("place", "chrome", "top_right", None),
            "Firefox abajo izquierda": ("place", "firefox", "bottom_left", None),
            "Explorador esquina inferior derecha": ("place", "explorador", "bottom_right", None),
            "Chrome arriba": ("place", "chrome", "top", None),
            "Chrome mitad inferior": ("place", "chrome", "bottom", None),
            "centra VSCode en la pantalla principal": ("place", "vscode", "center", 0),
            "cierra la ventana de Chrome": ("close", "chrome"),
            "restaura Firefox": ("restore", "firefox"),
            "enfoca Spotify": ("focus", "spotify"),
            "abre administrador de tareas": ("open", "administrador de tareas"),
            "Jarvis, minimiza Chrome": ("minimize", "chrome"),
            "silencia el sonido": ("system", "mute"),
            "sube volumen": ("system", "volume_up"),
            "captura de pantalla": ("system", "screenshot"),
            "bloquea el equipo": ("system", "lock"),
            "minimiza todas las ventanas": ("system", "minimize_all"),
            "Chrome izquierda monitor 0": None,
            "Chrome izquierda y reinicia": None,
            "": None,
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(parse(phrase), expected)

    def test_quarters_cover_odd_sized_negative_monitor(self):
        bounds = (-1921, -101, 0, 980)
        quarters = [rectangle(bounds, p, (800, 600)) for p in
                    ("top_left", "top_right", "bottom_left", "bottom_right")]
        self.assertEqual(sum(width * height for _, _, width, height in quarters), 1921*1081)
        self.assertEqual(quarters[0], (-1921, -101, 960, 540))
        self.assertEqual(quarters[3], (-961, 439, 961, 541))
        self.assertEqual(rectangle(bounds, "center", (800, 600)), (-1361, 139, 800, 600))
        self.assertEqual(rectangle(bounds, "monitor", (3000, 2000)), (-1921, -101, 1921, 1081))

    def test_dispatch_and_ambiguity(self):
        desktop = Mock()
        execute(desktop, "cierra Chrome")
        desktop.window_action.assert_called_once_with("close", "chrome")
        execute(desktop, "Chrome esquina inferior derecha monitor 2")
        desktop.move.assert_called_once_with("chrome", "bottom_right", 2)
        execute(desktop, "abre Chrome")
        desktop.open_app.assert_called_once_with("chrome")
        windows = [(1, "A - Visual Studio Code", "Code"), (2, "B - Visual Studio Code", "Code")]
        self.assertEqual(len(matching_windows(windows, "vscode")), 2)
        self.assertEqual(matching_windows(windows, "b - visual studio code"), windows[1:])
        desktop = Desktop.__new__(Desktop)
        desktop.windows = lambda: windows
        desktop.api = Mock()
        self.assertIn("varias", execute(desktop, "cierra VSCode"))
        desktop.api.PostMessageW.assert_not_called()

    def test_builtin_open_does_not_require_start_menu(self):
        desktop = Desktop.__new__(Desktop)
        with patch("jarvis.os.startfile", create=True) as launch:
            self.assertIn("Solicité", execute(desktop, "abre configuración de sonido"))
            launch.assert_called_once_with("ms-settings:sound")

    def test_shortcut_release_and_close_message(self):
        desktop = Desktop.__new__(Desktop)
        desktop.api = Mock()
        desktop.system_action("screenshot")
        self.assertEqual([call.args[:3] for call in desktop.api.keybd_event.call_args_list],
                         [(91,0,0),(16,0,0),(83,0,0),(83,0,2),(16,0,2),(91,0,2)])
        desktop.select_window = lambda _: (123, "Mi documento", "")
        desktop.window_action("close", "Mi documento")
        desktop.api.PostMessageW.assert_called_once_with(123, 0x0010, 0, 0)


@unittest.skipUnless(sys.platform == "win32", "Requiere Windows")
class WindowsTest(unittest.TestCase):
    def test_owned_window_positions_and_normal_close(self):
        import tkinter as tk
        desktop = Desktop()
        root = tk.Tk()
        root.title("JARVIS native command test")
        root.geometry("640x400+50+50")
        root.update()
        title = root.title().lower()
        try:
            handle, _, _ = desktop.select_window(title)
            screens = desktop.screens()
            monitor = next(number for number, (_, primary) in screens.items() if primary)
            bounds = screens[monitor][0]
            for position in ("left", "right", "top", "bottom", "top_left",
                             "top_right", "bottom_left", "bottom_right", "center", "monitor"):
                result = desktop.move(title, position, monitor)
                root.update()
                self.assertIn("Coloqué", result)
                actual = w.RECT()
                self.assertTrue(desktop.api.GetWindowRect(handle, c.byref(actual)))
                self.assertGreaterEqual(actual.left, bounds[0])
                self.assertLessEqual(actual.right, bounds[2])
            desktop.move(title, "full", monitor)
            root.update()
            self.assertTrue(desktop.api.IsZoomed(handle))
            desktop.minimize(title)
            root.update()
            self.assertTrue(desktop.api.IsIconic(handle))
            desktop.window_action("restore", title)
            root.update()
            self.assertFalse(desktop.api.IsIconic(handle))
            self.assertFalse(desktop.api.IsZoomed(handle))
            requested = []
            root.protocol("WM_DELETE_WINDOW", lambda: requested.append(True))
            desktop.window_action("close", title)
            root.update()
            self.assertEqual(requested, [True])
            self.assertTrue(desktop.api.IsWindow(handle))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
