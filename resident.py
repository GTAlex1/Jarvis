"""Own the desktop session, tray and updater independently of the command panel."""
from collections import deque
from concurrent.futures import Future
from dataclasses import replace
from queue import Empty, SimpleQueue
import sys
from threading import Thread
import tkinter as tk
from tkinter import messagebox

from assistant import Assistant
from commands import parse
from preferences import (microphone_enabled, save_voice_settings, set_microphone,
                         set_startup, starts_with_windows, voice_settings)
from updater import VERSION, acknowledge_startup, install_update, latest_update
from voice_service import STATE_LABELS, VoiceService
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
        self.voice_options = voice_settings()
        self.voice_status = ("disabled" if self.microphone else "muted", "")
        self.voice_log = deque(maxlen=24)
        self.voice = VoiceService(
            self.request_voice,
            lambda state, detail: self.defer(self.show_voice_status, state, detail),
            lambda *catalog: self.defer(self.show_catalog, *catalog),
        )
        self.tray = WindowsTray(root, self.show, self.menu_items, self.run_action, self.defer)
        root.protocol("WM_DELETE_WINDOW", self.hide)

    def run(self, background):
        try:
            icon_added = self.tray.add_icon()
            if not background or not icon_added:
                self.show()
            self.root.after_idle(acknowledge_startup)
            self.root.after_idle(self.configure_voice)
            if self.packaged:
                self.root.after_idle(self.start_update)
            self.poll_events()
            self.root.mainloop()
        finally:
            self.closing = True
            self.voice.close()
            self.tray.close()

    def show(self):
        if self.closing:
            return
        if self.panel is None:
            self.panel = self.create_panel(
                self.root, self.submit, self.update_clicked, self.packaged, self.open_voice_settings,
            )
            self.refresh_update()
            self.panel.voice_status(*self.voice_status)
            for text, tag in self.voice_log:
                self.panel.voice_message(text, tag)
            self.voice_log.clear()
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
            ("Escucha permanente", self.voice_options.enabled, self.toggle_voice),
            ("Ajustes de voz…", False, self.open_voice_settings),
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
        self.configure_voice()

    def configure_voice(self):
        if not self.microphone or not self.voice_options.enabled:
            self.show_voice_status("disabled" if self.microphone else "muted", "")
        self.voice.configure(self.voice_options, self.microphone)

    def toggle_voice(self):
        self.save_voice(replace(self.voice_options, enabled=not self.voice_options.enabled))

    def save_voice(self, options):
        save_voice_settings(options)
        self.voice_options = options
        self.configure_voice()

    def open_voice_settings(self):
        self.show()
        self.panel.open_voice_settings(self.voice_options, self.save_voice, self.voice.refresh_catalog)

    def show_catalog(self, *catalog):
        if self.panel is not None:
            self.panel.voice_catalog(*catalog)

    def show_voice_status(self, state, detail):
        if state not in {"disabled", "muted"} and (not self.microphone or not self.voice_options.enabled):
            return
        self.voice_status = (state, detail)
        self.tray.set_tooltip(f"JARVIS · {STATE_LABELS[state]}")
        if self.panel is not None:
            self.panel.voice_status(state, detail)

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

    def is_exit_command(self, command):
        if parse(command) == ("exit",):
            self.quit()
            return True
        return False

    def submit(self, command):
        if self.is_exit_command(command):
            return False
        future = self.assistant.submit(command)
        future.add_done_callback(lambda completed: self.defer(self.finish_command, completed))
        return True

    @staticmethod
    def command_result(completed):
        try:
            return completed.result()
        except Exception as error:
            return f"No se pudo completar la orden: {error}"

    def finish_command(self, completed):
        self.panel.reply(self.command_result(completed))

    def request_voice(self, command):
        reply = Future()
        self.defer(self.dispatch_voice, command, reply)
        return reply

    def dispatch_voice(self, command, reply):
        if not self.microphone or not self.voice_options.enabled:
            reply.cancel()
            return
        if not reply.set_running_or_notify_cancel():
            return
        if self.is_exit_command(command):
            reply.set_result("")
            return
        self.record_voice(f"VOZ · {command}", "you")
        future = self.assistant.submit(command)
        future.add_done_callback(lambda completed: self.defer(self.finish_voice, completed, reply))

    def finish_voice(self, completed, reply):
        text = self.command_result(completed)
        self.record_voice(text, "reply")
        reply.set_result(text)

    def record_voice(self, text, tag):
        if self.panel is None:
            self.voice_log.append((text, tag))
        else:
            self.panel.voice_message(text, tag)

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
