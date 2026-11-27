"""Local profile administration for the Windows front end."""
from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from speakers import MAX_PROFILES, Profile, SAMPLES_REQUIRED, profile_name


class SpeakerDialog:
    def __init__(self, parent, profiles, save, record, cancel, error=""):
        self.window = window = tk.Toplevel(parent)
        window.title("JARVIS · Perfiles de voz")
        window.resizable(False, False)
        self.save = save
        self.record = record
        self.cancel = cancel
        self.profiles = tuple(profiles)
        self.samples = []
        self.recording = False

        layout = ttk.Frame(window, padding=16)
        layout.pack(fill="both", expand=True)
        ttk.Label(layout, text="Personas autorizadas").grid(row=0, column=0, sticky="w")
        self.entries = tk.Listbox(layout, width=46, height=6, exportselection=False)
        self.entries.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.entries.bind("<<ListboxSelect>>", self.select)
        controls = ttk.Frame(layout)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="Renombrar", command=self.rename).pack(side="left")
        ttk.Button(controls, text="Eliminar", command=self.remove).pack(side="left", padx=6)
        ttk.Button(controls, text="Renovar muestras", command=self.renew).pack(side="left")

        ttk.Label(layout, text="Nombre del perfil nuevo").grid(row=3, column=0, sticky="w", pady=(12, 2))
        self.name = ttk.Entry(layout)
        self.name.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            layout, wraplength=400,
            text="Graba tres frases distintas en un lugar tranquilo. Las firmas se cifran para esta cuenta. "
                 "Registra solo a personas que hayan dado su permiso.",
        ).grid(row=5, column=0, sticky="w", pady=6)
        actions = ttk.Frame(layout)
        actions.grid(row=6, column=0, sticky="ew")
        self.record_button = ttk.Button(actions, text="Grabar muestra", command=self.start)
        self.record_button.pack(side="left")
        self.save_button = ttk.Button(actions, text="Guardar perfil", command=self.enroll)
        self.save_button.pack(side="left", padx=6)
        ttk.Button(actions, text="Reiniciar muestras", command=self.reset).pack(side="left")
        self.status = ttk.Label(layout, wraplength=400, text=error)
        self.status.grid(row=7, column=0, sticky="w", pady=(8, 0))
        self.renew_id = None
        window.bind("<Destroy>", self.destroyed)
        self.refresh()

    def select(self, _event=None):
        indices = self.entries.curselection()
        return self.profiles[indices[0]] if indices else None

    def refresh(self):
        self.entries.delete(0, "end")
        for profile in self.profiles:
            self.entries.insert("end", profile.name)
        self.buttons()

    def buttons(self):
        count = len(self.samples)
        self.record_button.configure(text=f"Grabar muestra {min(count + 1, SAMPLES_REQUIRED)}/{SAMPLES_REQUIRED}",
                                     state="normal" if count < SAMPLES_REQUIRED and not self.recording else "disabled")
        self.save_button.configure(state="normal" if count == SAMPLES_REQUIRED and not self.recording else "disabled")

    def write(self, profiles):
        try:
            self.save(profiles)
        except (OSError, ValueError) as error:
            messagebox.showerror("JARVIS", str(error), parent=self.window)
            return False
        self.profiles = tuple(profiles)
        self.refresh()
        return True

    def rename(self):
        profile = self.select()
        if profile is None:
            return
        name = simpledialog.askstring("Renombrar perfil", "Nombre nuevo", initialvalue=profile.name, parent=self.window)
        if name is None:
            return
        try:
            name = profile_name(name)
        except ValueError as error:
            self.status.configure(text=str(error))
            return
        self.write(tuple(replace(item, name=name) if item.id == profile.id else item for item in self.profiles))

    def remove(self):
        profile = self.select()
        if profile and messagebox.askyesno("JARVIS", f"¿Eliminar el perfil «{profile.name}»?",
                                           parent=self.window, default="no"):
            self.write(tuple(item for item in self.profiles if item.id != profile.id))
            if profile.id == self.renew_id:
                self.reset()

    def renew(self):
        profile = self.select()
        if profile is None or self.recording:
            return
        self.reset()
        self.renew_id = profile.id
        self.name.delete(0, "end")
        self.name.insert(0, profile.name)
        self.status.configure(text=f"Graba tres muestras nuevas para «{profile.name}».")

    def reset(self):
        if self.recording:
            return
        self.samples.clear()
        self.renew_id = None
        self.status.configure(text="")
        self.buttons()

    def start(self):
        self.recording = True
        self.status.configure(text="Preparando el micrófono…")
        self.buttons()
        self.record(self.progress, self.completed)

    def progress(self, message):
        if self.window.winfo_exists():
            self.status.configure(text=message)

    def completed(self, sample, message):
        if not self.window.winfo_exists():
            return
        self.recording = False
        if sample is not None:
            self.samples.append(sample)
        self.progress(message)
        self.buttons()

    def enroll(self):
        profiles = tuple(item for item in self.profiles if item.id != self.renew_id)
        if len(profiles) >= MAX_PROFILES:
            self.status.configure(text="Se ha alcanzado el límite de perfiles.")
            return
        try:
            profile = Profile.enroll(self.name.get(), self.samples)
        except ValueError as error:
            self.status.configure(text=str(error))
            return
        if self.write((*profiles, profile)):
            self.reset()
            self.name.delete(0, "end")
            self.status.configure(text=f"Perfil «{profile.name}» guardado en este equipo.")

    def destroyed(self, event):
        if event.widget is self.window:
            self.cancel()
            self.samples.clear()
