"""Local profile administration for the Windows front end."""
from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from speakers import ENROLLMENT_FRAMES, MAX_PROFILES, MIN_FRAMES, Profile, SAMPLES_REQUIRED, identify, profile_name


class SpeakerDialog:
    def __init__(self, parent, profiles, save, record, cancel, export, threshold, error=""):
        self.window = window = tk.Toplevel(parent)
        window.title("JARVIS · Perfiles de voz")
        window.resizable(False, False)
        self.save = save
        self.record = record
        self.cancel = cancel
        self.profiles = tuple(profiles)
        self.samples = [None] * SAMPLES_REQUIRED
        self.qualities = ["Pendiente"] * SAMPLES_REQUIRED
        self.tested = None
        self.export, self.threshold = export, threshold
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
        self.sample_rows = tk.Listbox(layout, width=62, height=SAMPLES_REQUIRED, exportselection=False)
        self.sample_rows.grid(row=6, column=0, sticky="ew", pady=4)
        actions = ttk.Frame(layout)
        actions.grid(row=7, column=0, sticky="ew")
        self.record_button = ttk.Button(actions, text="Grabar / repetir muestra", command=self.start)
        self.record_button.pack(side="left")
        self.check_button = ttk.Button(actions, text="Comprobar registro", command=self.check_enrollment)
        self.check_button.pack(side="left", padx=6)
        self.save_button = ttk.Button(actions, text="Guardar perfil", command=self.enroll)
        self.save_button.pack(side="left")
        extras = ttk.Frame(layout)
        extras.grid(row=8, column=0, sticky="ew", pady=4)
        ttk.Button(extras, text="Probar perfil seleccionado", command=self.test_profile).pack(side="left")
        ttk.Button(extras, text="Exportar diagnóstico…", command=self.export_info).pack(side="left", padx=6)
        ttk.Button(extras, text="Reiniciar muestras", command=self.reset).pack(side="left")
        self.status = ttk.Label(layout, wraplength=480, text=error)
        self.status.grid(row=9, column=0, sticky="w", pady=(8, 0))
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
        self.record_button.configure(state="disabled" if self.recording else "normal")
        ready = all(self.samples) and not self.recording
        self.check_button.configure(state="normal" if ready else "disabled")
        self.save_button.configure(state="normal" if ready and self.tested else "disabled")
        selected = self.sample_rows.curselection()
        self.sample_rows.delete(0, "end")
        for index, quality in enumerate(self.qualities, 1):
            self.sample_rows.insert("end", f"Muestra {index} · {quality}")
        if selected:
            self.sample_rows.selection_set(selected[0])

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
        self.samples[:] = [None] * SAMPLES_REQUIRED
        self.qualities[:] = ["Pendiente"] * SAMPLES_REQUIRED
        self.tested = None
        self.renew_id = None
        self.status.configure(text="")
        self.buttons()

    def start(self):
        if self.recording:
            return
        selected = self.sample_rows.curselection()
        index = selected[0] if selected else next((i for i, sample in enumerate(self.samples) if sample is None), 0)
        self.tested = None
        self.begin(lambda sample, message: self.complete_sample(index, sample, message), ENROLLMENT_FRAMES)

    def begin(self, callback, minimum):
        self.recording = True
        self.status.configure(text="Preparando el micrófono…")
        self.buttons()
        self.record(self.progress, callback, minimum)

    def progress(self, message):
        if self.window.winfo_exists():
            self.status.configure(text=message)

    def complete_sample(self, index, sample, message):
        if not self.window.winfo_exists():
            return
        self.recording = False
        self.samples[index], self.qualities[index] = sample, message
        self.sample_rows.selection_clear(0, "end")
        self.progress(message)
        self.buttons()

    def check_enrollment(self):
        try:
            profile = Profile.enroll(self.name.get(), self.samples)
        except ValueError as error:
            self.progress(str(error))
            return
        candidates = tuple(item for item in self.profiles if item.id != self.renew_id)
        self.tested = None
        self.begin(lambda sample, text: self.complete_test(profile, (*candidates, profile), sample, text, True), MIN_FRAMES)

    def test_profile(self):
        profile = self.select()
        if profile is not None and not self.recording:
            self.begin(lambda sample, text: self.complete_test(profile, self.profiles, sample, text, False), MIN_FRAMES)

    def complete_test(self, profile, candidates, sample, message, enrollment):
        if not self.window.winfo_exists():
            return
        self.recording = False
        if sample is not None:
            matched = identify(sample, candidates, self.threshold() / 100, expected=profile.id) == profile.id
            score = round(profile.score(sample.vector) * 100)
            label = "Coincide" if matched else "Sin coincidencia suficiente o perfil ambiguo"
            message = f"{label} · puntuación {score}/100 · mínimo {self.threshold()}/100. {message}"
            if matched and enrollment:
                self.tested = profile
        self.progress(message)
        self.buttons()

    def export_info(self):
        try:
            self.export(self.window)
        except OSError as error:
            self.progress(f"No se pudo exportar el diagnóstico: {error}")

    def enroll(self):
        profiles = tuple(item for item in self.profiles if item.id != self.renew_id)
        if len(profiles) >= MAX_PROFILES:
            self.status.configure(text="Se ha alcanzado el límite de perfiles.")
            return
        if self.tested is None:
            return
        try:
            profile = replace(self.tested, name=profile_name(self.name.get()))
        except ValueError as error:
            self.progress(str(error))
            return
        if self.write((*profiles, profile)):
            self.reset()
            self.name.delete(0, "end")
            self.status.configure(text=f"Perfil «{profile.name}» guardado en este equipo.")

    def destroyed(self, event):
        if event.widget is self.window:
            self.cancel()
            self.samples.clear()
