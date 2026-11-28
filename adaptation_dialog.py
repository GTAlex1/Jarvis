"""Local editor for voluntarily saved pronunciations and corrections."""
import tkinter as tk
from tkinter import messagebox, ttk

from voice_adaptation import Adaptation


class AdaptationDialog:
    def __init__(self, parent, settings, save):
        self.window = tk.Toplevel(parent)
        self.window.title("JARVIS · Adaptación de voz")
        layout = ttk.Frame(self.window, padding=14)
        layout.pack(fill="both", expand=True)
        self.save = save
        self.enabled = tk.BooleanVar(value=settings.enabled)
        self.aliases = list(settings.aliases)
        ttk.Checkbutton(layout, text="Usar mis correcciones y pronunciaciones", variable=self.enabled).grid(
            row=0, columnspan=2, sticky="w")
        self.entries = tk.Listbox(layout, width=58, height=7, exportselection=False)
        self.entries.grid(row=1, columnspan=2, sticky="ew", pady=6)
        self.entries.bind("<<ListboxSelect>>", self.select)
        self.variant = self.field(layout, 2, "Texto oído o pronunciación alternativa")
        self.canonical = self.field(layout, 3, "Nombre exacto de la aplicación")
        buttons = ttk.Frame(layout)
        buttons.grid(row=4, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Añadir / editar", command=self.edit).pack(side="left")
        ttk.Button(buttons, text="Eliminar", command=self.delete).pack(side="left", padx=4)
        ttk.Button(buttons, text="Restablecer", command=self.reset).pack(side="left")
        ttk.Button(buttons, text="Guardar", command=self.commit).pack(side="right")
        ttk.Button(layout, text="Nueva entrada", command=self.clear).grid(row=5, columnspan=2, sticky="w", pady=(4, 0))
        self.refresh()

    @staticmethod
    def field(layout, row, label):
        ttk.Label(layout, text=label).grid(row=row, column=0, sticky="w", padx=(0, 7))
        entry = ttk.Entry(layout, width=26)
        entry.grid(row=row, column=1, sticky="ew")
        return entry

    def clear(self):
        self.entries.selection_clear(0, "end")
        self.variant.delete(0, "end")
        self.canonical.delete(0, "end")

    def select(self, _event=None):
        index = self.entries.curselection()
        if index:
            for widget, value in zip((self.variant, self.canonical), self.aliases[index[0]]):
                widget.delete(0, "end")
                widget.insert(0, value)

    def refresh(self):
        self.clear()
        self.entries.delete(0, "end")
        for alternative, name in self.aliases:
            self.entries.insert("end", f"{alternative}  →  {name}")

    def edit(self):
        index = self.entries.curselection()
        entries = self.aliases.copy()
        item = self.variant.get().strip(), self.canonical.get().strip()
        if index:
            entries[index[0]] = item
        else:
            entries.append(item)
        try:
            Adaptation(self.enabled.get(), tuple(entries))
        except ValueError as error:
            messagebox.showerror("JARVIS", str(error), parent=self.window)
            return
        self.aliases = entries
        self.refresh()

    def delete(self):
        if index := self.entries.curselection():
            del self.aliases[index[0]]
            self.refresh()

    def reset(self):
        if messagebox.askyesno("JARVIS", "¿Borrar las correcciones guardadas al aplicar los cambios?",
                               default="no", parent=self.window):
            self.aliases.clear()
            self.enabled.set(False)
            self.refresh()

    def commit(self):
        try:
            self.save(Adaptation(self.enabled.get(), tuple(self.aliases)))
        except (OSError, ValueError) as error:
            messagebox.showerror("JARVIS", str(error), parent=self.window)
        else:
            self.window.destroy()
