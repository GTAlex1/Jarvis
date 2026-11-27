"""Own the desktop session, tray and updater independently of the command panel."""
from queue import Empty, SimpleQueue
import sys
from threading import Thread
import tkinter as tk
from tkinter import messagebox

from assistant import Assistant
from commands import parse
from preferences import microphone_enabled, set_microphone, set_startup, starts_with_windows
from updater import VERSION, acknowledge_startup, install_update, latest_update
from windows_tray import WindowsTray, show_running_instance, single_instance


class Resident:
    def __init__(self, root, assistant, create_panel):
        self.root = root
        self.assistant = assistant
        self.create_panel = create_panel
        self.panel = None
        self.events = SimpleQueue()
        self.available_update = None
        self.update_busy = False
        self.installing = False
        self.closing = False
        self.update_status = f"Versión {VERSION}"
        self.packaged = getattr(sys, "frozen", False)
        self.microphone = microphone_enabled()
        self.autostart = starts_with_windows()
        self.tray = WindowsTray(root, self.show, self.menu_items, self.run_action, self.defer)
        root.protocol("WM_DELETE_WINDOW", self.hide)

    def run(self, background):
        try:
            icon_added = self.tray.add_icon()
            if not background or not icon_added:
                self.show()
            self.root.after_idle(acknowledge_startup)
            if self.packaged:
                self.root.after_idle(self.start_update)
            self.poll_events()
            self.root.mainloop()
        finally:
            self.closing = True
            self.tray.close()

    def show(self):
        if self.closing:
            return
        if self.panel is None:
            self.panel = self.create_panel(self.root, self.submit, self.update_clicked, self.packaged)
            self.refresh_update()
        self.root.deiconify()
        self.root.lift()
        self.panel.focus()

    def hide(self):
        # Keep a way back into the panel if Explorer is still starting.
        if self.tray.visible:
            self.root.withdraw()
        else:
            self.root.iconify()

    def menu_items(self):
        return (
            ("Abrir JARVIS", False, self.show),
            ("Micrófono", self.microphone, self.toggle_microphone),
            ("Iniciar con Windows", self.autostart, self.toggle_startup),
            None,
            ("Salir de JARVIS", False, self.quit),
        )

    def run_action(self, action):
        if self.closing:
            return
        try:
            action()
        except (OSError, ValueError) as error:
            self.show()
            messagebox.showerror("JARVIS", str(error), parent=self.root)

    def toggle_microphone(self):
        desired = not self.microphone
        set_microphone(desired)
        self.microphone = desired

    def toggle_startup(self):
        desired = not self.autostart
        set_startup(desired)
        self.autostart = desired

    def quit(self):
        if self.installing:
            messagebox.showinfo("JARVIS", "La actualización cerrará JARVIS cuando termine de descargarse.",
                                parent=self.root)
        else:
            self.stop()

    def stop(self):
        self.closing = True
        self.root.quit()

    def defer(self, callback, *args):
        if not self.closing:
            self.events.put((callback, args))

    def submit(self, command):
        if parse(command) == ("exit",):
            self.quit()
            return False
        future = self.assistant.submit(command)
        future.add_done_callback(lambda completed: self.defer(self.finish_command, completed))
        return True

    def finish_command(self, completed):
        try:
            reply = completed.result()
        except Exception as error:
            reply = f"No se pudo completar la orden: {error}"
        self.panel.reply(reply)

    def deliver(self):
        while not self.closing:
            try:
                callback, args = self.events.get_nowait()
            except Empty:
                return
            callback(*args)

    def poll_events(self):
        self.deliver()
        if not self.closing:
            visible = self.root.state() in {"normal", "zoomed"}
            self.root.after(60 if visible else 200, self.poll_events)

    def refresh_update(self):
        if self.panel is not None and self.packaged:
            self.panel.update_controls(self.update_status, self.available_update, self.update_busy)

    def update_clicked(self):
        if self.available_update is None:
            self.start_update()
        elif messagebox.askyesno("JARVIS", f"¿Instalar {self.available_update[0]} y reiniciar JARVIS?",
                                 parent=self.root):
            self.start_update(self.available_update)

    def start_update(self, update=None):
        if self.update_busy or self.closing:
            return
        self.update_busy = True
        self.installing = update is not None
        self.update_status = "Descargando…" if self.installing else "Buscando…"
        self.refresh_update()

        def work():
            try:
                result = install_update(update) if update else latest_update()
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.defer(self.finish_update, None, str(error))
            else:
                self.defer(self.finish_update, result, None)

        Thread(target=work, name="jarvis-update", daemon=True).start()

    def finish_update(self, result, error):
        installing = self.installing
        self.installing = self.update_busy = False
        if installing and error is None:
            self.stop()
            return
        if error is None:
            self.available_update = result
            self.update_status = f"Disponible {result[0]}" if result else f"Versión {VERSION} · al día"
        else:
            self.update_status = "Error de actualización"
            if installing:
                self.show()
                messagebox.showerror("JARVIS", error, parent=self.root)
        self.refresh_update()


def launch(create_panel, background):
    with single_instance() as first:
        if not first:
            if not background and not show_running_instance():
                messagebox.showinfo("JARVIS", "Ya hay una instancia de JARVIS en ejecución.")
            return 0

        assistant = Assistant()
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            Resident(root, assistant, create_panel).run(background)
        except (OSError, tk.TclError) as error:
            messagebox.showerror("JARVIS", f"No se pudo iniciar JARVIS.\n{error}", parent=root)
            return 1
        finally:
            if root is not None:
                root.destroy()
            assistant.close()
    return 0
