"""Own the desktop session, tray and updater independently of the command panel."""
from collections import deque
from concurrent.futures import Future
from dataclasses import replace
from queue import Empty, SimpleQueue
from subprocess import SubprocessError
import os
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import json
from pathlib import Path

from assistant import Assistant
from adaptation_dialog import AdaptationDialog
from commands import clean, parse
from permissions import BUTTON, CODE, HOTKEY, VERBAL, classify
from security_dialog import SecurityDialog
from dialogue import Clarification, SelectedCommand
from preferences import (application_folders, save_application_folders, microphone_enabled, save_voice_settings, set_microphone,
                         set_startup, starts_with_windows, voice_settings, security_settings, save_security_settings,
                         adaptation_settings, save_adaptation_settings, update_channel, save_update_channel, save_lifecycle_settings)
from speaker_dialog import SpeakerDialog
from voice_authorization import (ApprovalAnswer, ExitAction, LocalApproval, PendingApproval,
                                 PowerAction, PowerScheduled, RejectedAction, UNVERIFIED)
from windows_protection import ProfileStore
from updater import VERSION, acknowledge_startup, install_update, latest_update, version_tuple
from voice_service import STATE_LABELS, VoiceService
from windows_tray import (WindowsTray, handover_kind, native_instance, request_handover,
                          show_running_instance, single_instance)
from voice_diagnostics import LOG, configure as configure_log
from windows_actions import perform_power
from app_catalog import name_key
from voice_context import ContextOrder
import english_voice


class Resident:
    def __init__(self, root, assistant, create_panel):
        self.root = root
        self.assistant = assistant
        self.assistant.desktop.on_launch = lambda result: self.defer(self.report_launch, result)
        self.create_panel = create_panel
        self.panel = None
        self.events = SimpleQueue()
        self.available_update = None
        self.update_channel = update_channel()
        self.return_to_stable = False
        self.update_busy = False
        self.installing = False
        self.closing = False
        self.restart_requested = False
        self.hidden_notice = False
        self.running_commands = 0
        self.language_busy = False
        self.english_requested = False
        self.last_correction = None
        self.update_status = f"Versión {VERSION}"
        self.packaged = getattr(sys, "frozen", False)
        self.microphone = microphone_enabled()
        self.autostart = starts_with_windows()
        self.voice_options = voice_settings()
        self.policy = security_settings()
        self.security_dialog = None
        self.adaptation_dialog = None
        self.adaptation = adaptation_settings()
        self.revision = 0
        self.power_job = None
        configure_log()
        self.profile_store = ProfileStore()
        self.profile_error = ""
        self.speaker_dialog = None
        self.pending_approval = None
        try:
            self.profiles = self.profile_store.load()
        except (OSError, ValueError) as error:
            self.profiles = ()
            self.profile_error = f"No se pudieron leer los perfiles protegidos: {error}"
        self.voice_status = ("disabled" if self.microphone else "muted", "")
        self.voice_log = deque(maxlen=24)
        self.voice = VoiceService(
            self.request_voice,
            lambda state, detail: self.defer(self.show_voice_status, state, detail),
            lambda *catalog: self.defer(self.show_catalog, *catalog),
            lambda result: self.defer(self.show_test, result),
            lambda speaker: self.defer(self.cancel_pending, speaker),
        )
        self.voice.context_names = self.assistant.desktop.context_names
        self.voice.set_security(self.policy.biometrics)
        self.voice.set_adaptation(self.adaptation)
        self.voice.set_profiles(self.profiles, self.profile_error)
        self.tray = WindowsTray(root, self.show, self.menu_items, self.run_action, self.defer, self.accept_handover)
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
                self.root, self.submit, self.update_clicked, self.packaged, self.open_voice_settings, self.open_security,
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
            if not self.hidden_notice:
                self.hidden_notice = True
                self.tray.notify_background()
        else:
            self.root.iconify()

    def menu_items(self):
        return (
            ("Abrir JARVIS", False, self.show),
            ("Micrófono", self.microphone, self.toggle_microphone),
            ("Iniciar con Windows", self.autostart, self.toggle_startup),
            ("Escucha permanente", self.voice_options.enabled, self.toggle_voice),
            ("Configuración de voz…", False, self.open_voice_settings),
            ("Voz en español", self.voice_options.language == "es", self.use_spanish),
            ("Voz en inglés…", self.voice_options.language == "en", self.use_english),
            ("Perfiles de voz…", False, self.open_speakers),
            ("Adaptación de voz…", False, self.open_adaptation),
            *((("Guardar última corrección…", False, self.save_last_correction),) if self.last_correction else ()),
            ("Seguridad y permisos…", False, self.open_security),
            ("Añadir carpeta de aplicaciones…", False, self.configure_application_folders),
            ("Quitar carpetas adicionales…", False, self.clear_application_folders),
            *((("Cierre de videojuegos y launchers…", self.assistant.desktop.lifecycle_settings.enabled,
                self.configure_lifecycle),) if hasattr(self, "assistant") and "configure_lifecycle" in dir(self) else ()),
            ("Confirmar acción de voz…", False, self.confirm_voice),
            ("Detener respuesta de voz / cancelar acción", False, self.cancel_voice),
            None,
            *((("Canal estable", self.update_channel == "stable", lambda: self.change_channel("stable")),
               ("Canal experimental", self.update_channel == "experimental", lambda: self.change_channel("experimental")))
              if hasattr(self, "update_channel") else ()),
            (("Actualizar y reiniciar…" if self.available_update else "Buscar actualizaciones"), False, self.update_clicked),
            ("Reiniciar JARVIS", False, self.restart),
            ("Salir completamente", False, self.quit),
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
        self.invalidate_voice()
        self.configure_voice()

    def configure_voice(self):
        if not self.microphone or not self.voice_options.enabled:
            self.show_voice_status("disabled" if self.microphone else "muted", "")
        self.voice.configure(self.voice_options, self.microphone)

    def toggle_voice(self):
        self.save_voice(replace(self.voice_options, enabled=not self.voice_options.enabled))

    def save_voice(self, options):
        save_voice_settings(options)
        self.invalidate_voice()
        self.voice_options = options
        self.configure_voice()

    def open_voice_settings(self):
        self.show()
        self.panel.open_voice_settings(
            self.voice_options, lambda options: self.save_voice(replace(options, language=self.voice_options.language)), self.voice.refresh_catalog,
            self.voice.test_microphone, self.voice.cancel_test, lambda: self.voice.meter,
            lambda: self.voice.test_progress,
        )

    def use_spanish(self):
        self.english_requested = False
        self.save_voice(replace(self.voice_options, language="es"))

    def use_english(self):
        self.english_requested = True
        if self.language_busy:
            return
        if english_voice.installed():
            self.save_voice(replace(self.voice_options, language="en"))
            return
        if not messagebox.askyesno("JARVIS", "¿Descargar el modelo local de inglés (41 MB)?",
                                   parent=self.root):
            return
        self.language_busy = True

        def install_model():
            try:
                english_voice.install()
            except (OSError, ValueError) as error:
                self.defer(self.finish_language, str(error))
            else:
                self.defer(self.finish_language, "")

        Thread(target=install_model, name="jarvis-language", daemon=True).start()

    def finish_language(self, error):
        self.language_busy = False
        if error:
            self.show()
            messagebox.showerror("JARVIS", error, parent=self.root)
        elif self.english_requested:
            self.save_voice(replace(self.voice_options, language="en"))
            self.record_voice("El reconocimiento en inglés está preparado.", "reply")

    def save_last_correction(self):
        if not self.last_correction:
            return
        alternative, canonical, expires = self.last_correction
        if monotonic() > expires:
            self.last_correction = None
            raise ValueError("La corrección ha caducado. Puedes escribirla en Adaptación de voz.")
        options = self.adaptation.corrected(alternative, canonical)
        if messagebox.askyesno("JARVIS", f"¿Guardar «{alternative}» como pronunciación de «{canonical}»?",
                               default="no", parent=self.root):
            self.save_adaptation(options)
            self.last_correction = None

    def open_adaptation(self):
        if self.adaptation_dialog is not None and self.adaptation_dialog.window.winfo_exists():
            self.adaptation_dialog.window.lift()
            return
        self.adaptation_dialog = AdaptationDialog(self.root, self.adaptation, self.save_adaptation)

    def save_adaptation(self, options):
        save_adaptation_settings(options)
        self.invalidate_voice()
        self.adaptation = options
        self.voice.set_adaptation(options)

    def open_security(self):
        if self.security_dialog is not None and self.security_dialog.window.winfo_exists():
            self.security_dialog.window.lift()
            return
        self.security_dialog = SecurityDialog(self.root, self.policy, self.save_security, self.open_speakers)

    def save_security(self, policy):
        # This is only a local UI callback. Commands cannot invoke it.
        save_security_settings(policy)
        self.invalidate_voice()
        self.policy = policy
        self.voice.set_security(policy.biometrics)
        LOG.info("permisos: configuración modificada desde interfaz local")

    def open_speakers(self):
        if self.speaker_dialog is not None and self.speaker_dialog.window.winfo_exists():
            self.speaker_dialog.window.lift()
            return
        self.speaker_dialog = SpeakerDialog(self.root, self.profiles, self.save_profiles, self.record_speaker,
                                            self.voice.cancel_enrollment, self.export_diagnostics,
                                            lambda: self.voice_options.speaker_threshold, self.profile_error)

    def save_profiles(self, profiles):
        self.profile_store.save(profiles)
        self.invalidate_voice()
        self.profiles = tuple(profiles)
        self.profile_error = ""
        self.voice.set_profiles(self.profiles)

    def record_speaker(self, progress, done, minimum):
        self.voice.record_speaker(lambda message: self.defer(progress, message),
                                  lambda sample, message: self.defer(done, sample, message), minimum)

    def export_diagnostics(self, parent):
        target = filedialog.asksaveasfilename(parent=parent, defaultextension=".json",
                                             initialfile="jarvis-biometria.json",
                                             filetypes=[("Diagnóstico JSON", "*.json")])
        if target:
            snapshot = {"version": VERSION, "captura": self.voice.current_route,
                        "biometria": dict(self.voice.last_biometrics),
                        "eventos": list(self.voice.recent_stages.copy()),
                        "verificacion_activa": self.policy.biometrics,
                        "umbral": self.voice_options.speaker_threshold,
                        "estado_perfiles": "ilegible" if self.profile_error else ("disponibles" if self.profiles else "ausentes")}
            Path(target).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def show_catalog(self, *catalog):
        if self.panel is not None:
            self.panel.voice_catalog(*catalog)

    def show_test(self, result):
        if self.panel is not None:
            self.panel.voice_test(result)

    def report_launch(self, result):
        self.record_voice(result.message, "reply")
        self.voice.trace("resultado", "arranque_" + result.state)

    def show_voice_status(self, state, detail):
        if state not in {"disabled", "muted"} and (not self.microphone or not self.voice_options.enabled):
            return
        self.voice_status = (state, detail)
        self.tray.set_state("executing" if self.running_commands and state in {"waiting", "disabled", "muted"} else state)
        if self.panel is not None:
            self.panel.voice_status(state, detail)

    def toggle_startup(self):
        desired = not self.autostart
        set_startup(desired)
        self.autostart = desired

    def accept_handover(self):
        if not self.installing and not self.closing and messagebox.askyesno(
            "JARVIS", "Otra versión de JARVIS ha solicitado iniciar. ¿Cerrar esta sesión?",
            default="no", parent=self.root,
        ):
            self.stop()

    def restart(self):
        if self.installing:
            self.quit()
            return
        self.restart_requested = True
        self.stop()

    def quit(self):
        if self.installing:
            messagebox.showinfo("JARVIS", "La actualización cerrará JARVIS cuando termine de descargarse.",
                                parent=self.root)
        else:
            self.stop()

    def stop(self):
        self.invalidate_voice()
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
        if parse(command) in (("system", "shutdown"), ("system", "restart")):
            if messagebox.askyesno("JARVIS", "¿Programar la operación dentro de diez segundos?",
                                   default="no", parent=self.root):
                self.panel.reply(self.schedule_power(PowerAction(parse(command)[1])).message)
            return True
        if self.is_exit_command(command):
            return False
        self.running_commands += 1
        self.tray.set_state("executing")
        future = self.assistant.submit(command)
        future.add_done_callback(lambda completed: self.defer(self.finish_command, completed, command))
        return True

    @staticmethod
    def command_result(completed):
        try:
            return completed.result()
        except Exception as error:
            return f"No se pudo completar la orden: {error}"

    def configure_lifecycle(self):
        from lifecycle import LifecycleSettings

        current = self.assistant.desktop.lifecycle_settings
        enabled = messagebox.askyesnocancel("JARVIS", "¿Cerrar también el launcher si se verifica que está libre?",
                                            default="yes" if current.enabled else "no", parent=self.root)
        if enabled is None:
            return
        providers = simpledialog.askstring("JARVIS", "Proveedores que se quedarán abiertos, separados por comas.",
                                           initialvalue=", ".join(current.providers), parent=self.root)
        if providers is None:
            return
        games = simpledialog.askstring("JARVIS", "Juegos cuyo launcher se quedará abierto, separados por comas.",
                                       initialvalue=", ".join(current.games), parent=self.root)
        if games is None:
            return
        value = LifecycleSettings(enabled, tuple(name_key(item).replace(" ", "") for item in providers.split(",") if item.strip()),
                                  tuple(name_key(item) for item in games.split(",") if item.strip()))
        save_lifecycle_settings(value)
        self.assistant.desktop.lifecycle_settings = value

    def configure_application_folders(self):
        current = application_folders()
        selected = filedialog.askdirectory(parent=self.root, title="Añadir una carpeta de aplicaciones o juegos")
        if selected:
            path = Path(selected)
            if path.anchor == str(path):
                raise ValueError("Elige una carpeta concreta dentro de la unidad.")
            updated = tuple(dict.fromkeys((*current, str(path))))
            save_application_folders(updated)
            self.assistant.desktop.index.refresh(force=True)

    def clear_application_folders(self):
        if application_folders() and messagebox.askyesno("JARVIS", "¿Quitar todas las carpetas adicionales del catálogo?",
                                                        default="no", parent=self.root):
            save_application_folders(())
            self.assistant.desktop.index.refresh(force=True)

    def finish_command(self, completed, command):
        self.running_commands -= 1
        self.tray.set_state("executing" if self.running_commands else self.voice_status[0])
        result = self.command_result(completed)
        if not isinstance(result, Clarification):
            self.panel.reply(result)
            return
        choice = simpledialog.askinteger("Selecciona el destino", result.written + "\n\nNúmero de la opción:",
                                         parent=self.root, minvalue=1, maxvalue=len(result.options))
        if choice is None:
            self.panel.reply("Orden cancelada.")
            return
        self.running_commands += 1
        self.tray.set_state("executing")
        future = self.assistant.submit(SelectedCommand(command, result.options[choice - 1]))
        future.add_done_callback(lambda finished: self.defer(self.finish_command, finished, command))

    def can_use_voice(self, speaker, revision=None):
        if self.closing or not self.microphone or not self.voice_options.enabled:
            return False
        if revision is not None and revision != self.revision:
            return False
        return (any(profile.id == speaker for profile in self.profiles) if self.policy.biometrics
                else speaker == UNVERIFIED)

    def request_voice(self, command, speaker):
        reply = Future()
        self.defer(self.dispatch_voice, command, speaker, reply, self.revision)
        return reply

    def dispatch_voice(self, command, speaker, reply, revision=None):
        if not self.can_use_voice(speaker, revision):
            LOG.info("permisos: rechazada motivo=voz_no_autorizada_o_sesion_cambiada")
            reply.cancel()
            return
        if not reply.set_running_or_notify_cancel():
            return
        revision = self.revision if revision is None else revision
        if isinstance(command, ApprovalAnswer):
            request = self.pending_approval
            if not request or request.speaker != speaker or not request.matches(VERBAL, command.ticket):
                LOG.info("permisos: confirmación verbal sin solicitud vigente")
                reply.set_result("No hay una acción pendiente para esa confirmación.")
            elif command.yes:
                self.approve(request, reply)
            else:
                self.clear_approval()
                LOG.info("permisos: confirmación verbal cancelada")
                reply.set_result("Acción cancelada.")
            return
        self.clear_approval()
        source = command.command if isinstance(command, SelectedCommand) else command
        option = command.option.label if isinstance(command, SelectedCommand) else ""
        title = option or source
        self.record_voice(f"VOZ · {title}", "you")
        self.run_voice_action(command, speaker, revision, reply)

    def run_voice_action(self, command, speaker, revision, reply, approved=False):
        guard = lambda: self.can_use_voice(speaker, revision)
        future = self.assistant.submit_voice(command, approved=approved, guard=guard, policy=self.policy)
        source = command.command if isinstance(command, SelectedCommand) else command
        selected = clean(command.option.label) if isinstance(command, SelectedCommand) else ""
        category = classify(parse(source) or ("unknown",), selected)
        future.add_done_callback(lambda completed: self.defer(self.finish_voice, completed, speaker, reply,
                                                               revision, category, command))

    def finish_voice(self, completed, speaker, reply, revision, category, command=None):
        if not self.can_use_voice(speaker, revision):
            if reply is not None:
                reply.set_result("")
            return
        result = self.command_result(completed)
        if isinstance(result, LocalApproval):
            self.voice.trace("permiso", "requiere_confirmación")
            self.require_confirmation(result, speaker, reply)
            return
        if isinstance(result, ExitAction):
            if self.installing:
                result = RejectedAction("Hay una actualización instalándose.", "actualizacion")
            else:
                LOG.info("permisos: ejecutada categoría=close")
                if reply is not None:
                    reply.set_result("Cerrando JARVIS.")
                self.quit()
                return
        if isinstance(result, PowerAction):
            result = self.schedule_power(result, speaker, revision)
        if isinstance(result, RejectedAction):
            LOG.info("permisos: rechazada categoría=%s motivo=%s", category, result.reason)
            self.voice.trace("permiso" if result.reason == "politica" else "resultado", result.reason)
            result = result.message
        elif not isinstance(result, (Clarification, PowerScheduled)):
            LOG.info("permisos: orden despachada categoría=%s", category)
            self.voice.trace("permiso", "permitida")
            self.voice.trace("resultado", "solicitada_a_windows" if category == "open" else "devuelto_por_ejecutor")
        elif isinstance(result, Clarification):
            self.voice.trace("permiso", "destino_por_aclarar")
        if (isinstance(command, SelectedCommand) and isinstance(command.command, ContextOrder)
                and isinstance(result, str) and not result.startswith(("No pude", "No encontré", "Se canceló"))):
            intent = parse(command.command)
            name = command.option.label.split(" · ", 1)[0]
            if intent and len(intent) > 1 and name_key(intent[1]) != name_key(name):
                self.last_correction = (intent[1], name, monotonic() + 120)
        shown = result.written if isinstance(result, Clarification) else result.message if isinstance(result, PowerScheduled) else result
        self.record_voice(shown, "reply")
        if reply is not None:
            reply.set_result(result)

    def clear_approval(self):
        request, self.pending_approval = self.pending_approval, None
        if request and request.request.method == HOTKEY:
            self.tray.clear_hotkey()

    def require_confirmation(self, result, speaker, reply):
        self.clear_approval()
        request = PendingApproval.create(result, speaker, monotonic(), self.revision)
        self.pending_approval = request
        if result.method == HOTKEY and not self.tray.set_hotkey(lambda: self.approve_hotkey(request)):
            self.pending_approval = None
            LOG.info("permisos: rechazada categoría=%s motivo=atajo_no_disponible", result.category)
            reply.set_result("El atajo Control, Alt y F10 está ocupado. Revisa Seguridad y permisos.")
            return
        LOG.info("permisos: pendiente categoría=%s método=%s", result.category, result.method)
        self.record_voice(f"Pendiente de confirmación · {result.description}", "reply")
        reply.set_result(replace(result, ticket=request.ticket))

    def request_valid(self, request):
        return (request is self.pending_approval and request.valid(monotonic(), self.profiles, self.revision)
                and self.can_use_voice(request.speaker, request.revision))

    def approve_hotkey(self, request):
        if request.matches(HOTKEY, request.ticket):
            self.approve(request)

    def approve(self, request, reply=None):
        if not self.request_valid(request):
            if reply is not None:
                reply.set_result("La confirmación ya caducó.")
            return
        self.clear_approval()
        order = request.request.command
        LOG.info("permisos: aprobada categoría=%s método=%s", request.request.category, request.request.method)
        self.run_voice_action(order, request.speaker, request.revision, reply, approved=True)

    def confirm_voice(self):
        request = self.pending_approval
        if request is None or not self.request_valid(request):
            messagebox.showinfo("JARVIS", "No hay ninguna acción de voz pendiente.", parent=self.root)
            return
        method = request.request.method
        if method == CODE:
            entered = simpledialog.askstring(
                "Confirmar acción de voz",
                f"{request.request.description}\n\nEscribe el código {request.code} para autorizarla.",
                parent=self.root,
            )
            allowed = request.matches(CODE, request.ticket, entered)
        elif method == BUTTON:
            allowed = messagebox.askyesno("Confirmar acción de voz", request.request.description,
                                          parent=self.root, default="no")
        else:
            messagebox.showinfo("JARVIS", "Esta acción espera el método de confirmación configurado.",
                                parent=self.root)
            return
        if allowed:
            self.approve(request)
        elif self.pending_approval is request:
            self.clear_approval()
            LOG.info("permisos: rechazada categoría=%s motivo=confirmación_local", request.request.category)

    def schedule_power(self, result, speaker=None, revision=None):
        if self.power_job is not None:
            return PowerScheduled("Ya hay una operación de apagado o reinicio pendiente.")
        operation = result.operation
        verb = "apagar" if operation == "shutdown" else "reiniciar"
        token = object()
        callback = lambda: self.finish_power(token, operation, speaker, revision)
        self.power_job = token, self.root.after(10000, callback)
        LOG.info("permisos: cuenta atrás categoría=power acción=%s", operation)
        self.voice.trace("permiso", "cuenta_atrás")
        return PowerScheduled(f"Voy a {verb} el equipo en diez segundos. Di cancela para detener la operación.")

    def finish_power(self, token, operation, speaker, revision):
        if self.power_job is None or self.power_job[0] is not token:
            return
        self.power_job = None
        if self.closing or self.installing or (speaker is not None and not self.can_use_voice(speaker, revision)):
            LOG.info("permisos: cancelada categoría=power motivo=sesión")
            return
        try:
            perform_power(operation)
        except (OSError, ValueError, SubprocessError) as error:
            LOG.warning("permisos: rechazada categoría=power motivo=%s", type(error).__name__)
            self.record_voice("Windows no pudo apagar o reiniciar. Comprueba los permisos de la sesión.", "reply")
        else:
            LOG.info("permisos: ejecutada categoría=power acción=%s", operation)
            self.voice.trace("resultado", "solicitada_a_windows")

    def invalidate_voice(self):
        self.revision += 1
        self.clear_approval()
        if self.power_job is not None:
            self.root.after_cancel(self.power_job[1])
            self.power_job = None
            LOG.info("permisos: cancelada categoría=power")

    def cancel_pending(self, speaker=None):
        self.invalidate_voice()

    def cancel_voice(self):
        self.invalidate_voice()
        self.voice.stop_speech()

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
        if self.pending_approval and not self.request_valid(self.pending_approval):
            self.clear_approval()
            LOG.info("permisos: confirmación caducada")
        if not self.closing:
            visible = self.root.state() in {"normal", "zoomed"}
            self.root.after(60 if visible else 200, self.poll_events)

    def refresh_update(self):
        if self.panel is not None and self.packaged:
            self.panel.update_controls(self.update_status, self.available_update, self.update_busy)

    def change_channel(self, channel):
        if self.update_busy:
            return
        if channel == "experimental" and self.update_channel != channel and not messagebox.askyesno(
            "JARVIS", "Este canal ofrece versiones para pruebas. ¿Activarlo?", default="no", parent=self.root
        ):
            return
        if channel != self.update_channel:
            save_update_channel(channel)
            self.update_channel = channel
        self.available_update = None
        self.return_to_stable = channel == "stable"
        self.start_update()

    def update_clicked(self):
        if self.available_update is None:
            self.start_update()
        elif messagebox.askyesno("JARVIS", self.update_question(),
                                 parent=self.root):
            self.start_update(self.available_update)

    def update_question(self):
        tag = self.available_update[0]
        action = "Volver a la versión estable" if version_tuple(tag) < version_tuple(VERSION) else "Instalar"
        return f"¿{action} {tag} y reiniciar JARVIS?"

    def start_update(self, update=None):
        if self.update_busy or self.closing:
            return
        self.update_busy = True
        self.installing = update is not None
        self.update_status = "Descargando…" if self.installing else "Buscando…"
        self.refresh_update()

        def work():
            try:
                result = (install_update(update, check_policy=True) if update else latest_update(
                    self.update_channel, remote_policy=True, allow_stable_return=self.return_to_stable,
                ))
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


def restart_process():
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        args = [sys.executable]
    else:
        args = [sys.executable, str(Path(__file__).with_name("jarvis_gui.py"))]
    subprocess.Popen(args, env=env, shell=False)


def run_primary(create_panel, background):
    assistant = Assistant()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        resident = Resident(root, assistant, create_panel)
        resident.run(background)
        return 0, resident.restart_requested
    except (OSError, tk.TclError) as error:
        messagebox.showerror("JARVIS", f"No se pudo iniciar JARVIS.\n{error}", parent=root)
        return 1, False
    finally:
        if root is not None:
            root.destroy()
        assistant.close()


def check_handover():
    active = native_instance()
    if active is None and show_running_instance():
        active = native_instance()
    mode = handover_kind(active, VERSION)
    if mode == "existing":
        show_running_instance()
        return False
    name = f"JARVIS {active.version}" if active and active.version else "Otra instancia de JARVIS"
    if mode == "cooperative":
        return (messagebox.askyesno("JARVIS", f"{name} sigue en segundo plano. ¿Cerrar esa sesión e iniciar {VERSION}?",
                                    default="no") and request_handover(active))
    show_running_instance()
    return messagebox.askretrycancel(
        "JARVIS", f"{name} sigue ejecutándose. Selecciona «Salir de JARVIS» en su bandeja "
                  f"y pulsa Reintentar para iniciar JARVIS {VERSION}.", default="cancel")


def launch(create_panel, background):
    deadline = None
    while True:
        with single_instance() as first:
            if first:
                code, restart = run_primary(create_panel, background)
                break
        if background:
            return 0
        if deadline is None:
            if not check_handover():
                return 0
            deadline = monotonic() + 40
        elif monotonic() >= deadline:
            messagebox.showinfo("JARVIS", "La instancia activa sigue cerrándose o está instalando una actualización.")
            return 0
        sleep(0.15)
    if restart:
        try:
            restart_process()
        except OSError as error:
            messagebox.showerror("JARVIS", f"No se pudo reiniciar JARVIS.\n{error}")
            return 1
    return code
