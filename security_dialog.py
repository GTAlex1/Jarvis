"""Local security settings; changing policy always requires a desktop action."""
import tkinter as tk
from tkinter import messagebox, ttk

from permissions import CATEGORIES, LOCAL, METHODS, PRESETS, SecurityPolicy


class SecurityDialog:
    def __init__(self, parent, policy, save, profiles):
        self.window = window = tk.Toplevel(parent)
        window.title("JARVIS · Seguridad y permisos")
        layout = ttk.Frame(window, padding=14)
        layout.pack(fill="both", expand=True)
        self.save, self.original = save, policy
        self.mode, self.biometrics = tk.StringVar(value=policy.mode), tk.BooleanVar(value=policy.biometrics)
        ttk.Label(layout, text="Perfil de seguridad").grid(row=0, column=0, sticky="w")
        presets = ttk.Combobox(layout, textvariable=self.mode, values=(*PRESETS, "Personalizado"), state="readonly")
        presets.grid(row=0, column=1, sticky="ew")
        presets.bind("<<ComboboxSelected>>", self.refresh)
        ttk.Checkbutton(layout, text="Verificar el hablante", variable=self.biometrics).grid(row=1, column=0, sticky="w")
        ttk.Button(layout, text="Perfiles de voz…", command=profiles).grid(row=1, column=1, sticky="e")
        self.summary = ttk.Label(layout, wraplength=490)
        self.summary.grid(row=2, columnspan=2, sticky="w", pady=(4, 8))
        self.rules, self.boxes = {}, {}
        for pos, (category, info) in enumerate(CATEGORIES.items(), 3):
            value = self.rules[category] = tk.StringVar(value=METHODS[policy.method(category)])
            ttk.Label(layout, text=info.label).grid(row=pos, column=0, sticky="w")
            methods = (method for method in METHODS if method in LOCAL or not info.require_local)
            box = self.boxes[category] = ttk.Combobox(layout, textvariable=value,
                                                     values=tuple(METHODS[method] for method in methods),
                                                     state="readonly", width=25)
            box.grid(row=pos, column=1, sticky="ew", padx=(12, 0))
        ttk.Button(layout, text="Guardar", command=self.commit).grid(row=3+len(CATEGORIES), column=1,
                                                                    sticky="e", pady=(8, 0))
        self.refresh()

    def refresh(self, _event=None):
        mode = self.mode.get()
        summaries = {
            "Libertad": "Control vocal de las acciones habituales y de apagado sin pedir aprobación.",
            "Equilibrado": "Órdenes cotidianas directas. Confirmación verbal o local según el riesgo.",
            "Estricto": "Código temporal para las operaciones sensibles.",
            "Personalizado": "Elige un método por categoría. Las operaciones críticas conservan la aprobación local.",
        }
        self.summary.configure(text=summaries[mode])
        for name, box in self.boxes.items():
            if mode != "Personalizado":
                self.rules[name].set(METHODS[SecurityPolicy(mode).method(name)])
            box.configure(state="readonly" if mode == "Personalizado" else "disabled")

    def commit(self):
        mode, biometrics = self.mode.get(), self.biometrics.get()
        ids = {label: method for method, label in METHODS.items()}
        rules = {name: ids[value.get()] for name, value in self.rules.items()} if mode == "Personalizado" else {}
        policy = SecurityPolicy(mode, biometrics, rules)
        less_restrictive = mode == "Libertad" or not biometrics or any(
            policy.method(name) in {"allow", "verbal"} and
            self.original.method(name) not in {"allow", "verbal"} for name in CATEGORIES
        )
        if less_restrictive and not messagebox.askyesno(
            "Cambiar protección de voz",
            "Una llamada o una grabación puede provocar órdenes, incluso con verificación de voz. "
            "Desactivarla permite que cualquier persona audible dé órdenes. "
            "Los permisos sin confirmación se aplican en cuanto JARVIS acepte la orden. ¿Guardar estos cambios?",
            parent=self.window, default="no",
        ):
            return
        try:
            self.save(policy)
        except (OSError, ValueError) as error:
            messagebox.showerror("JARVIS", str(error), parent=self.window)
        else:
            self.window.destroy()
