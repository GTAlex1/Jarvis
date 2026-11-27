import sys
import tkinter as tk
from tkinter import scrolledtext, ttk

from jarvis import Desktop, execute, normalize


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 u 11 para controlar el escritorio.")
        return 1

    desktop = Desktop()
    root = tk.Tk()
    root.title("JARVIS")
    root.geometry("700x490")
    root.minsize(420, 340)
    root.configure(bg="#101827")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    tk.Label(
        root, text="JARVIS", bg="#101827", fg="#8be9fd",
        font=("Segoe UI", 24, "bold"),
    ).grid(row=0, column=0, sticky="w", padx=20, pady=(14, 8))

    history = scrolledtext.ScrolledText(
        root, wrap="word", bg="#172337", fg="#eef4ff", relief="flat",
        padx=12, pady=12, font=("Segoe UI", 11), state="disabled",
    )
    history.grid(row=1, column=0, sticky="nsew", padx=20)
    history.tag_configure("you", foreground="#8be9fd")

    def append(message, tag=None):
        history.configure(state="normal")
        history.insert("end", message + "\n", tag or ())
        history.configure(state="disabled")
        history.see("end")

    form = tk.Frame(root, bg="#101827")
    form.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 8))
    form.columnconfigure(0, weight=1)
    tk.Label(form, text="Escribe una orden", bg="#101827", fg="#eef4ff").grid(
        row=0, column=0, sticky="w"
    )
    entry = ttk.Entry(form, font=("Segoe UI", 11))
    entry.grid(row=1, column=0, sticky="ew", ipady=4)

    def run(command):
        if normalize(command) == "salir":
            root.destroy()
            return
        append(f"Tú · {command}", "you")
        try:
            response = execute(desktop, command)
        except OSError as error:
            response = f"No se pudo completar la orden: {error}"
        append(f"JARVIS · {response}\n")

    def submit(_event=None):
        command = entry.get().strip()
        if command:
            entry.delete(0, "end")
            run(command)

    ttk.Button(form, text="Enviar", command=submit).grid(row=1, column=1, padx=(8, 0))
    entry.bind("<Return>", submit)

    shortcuts = tk.Frame(root, bg="#101827")
    shortcuts.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 14))
    for command in ("pantallas", "ventanas", "ayuda"):
        ttk.Button(shortcuts, text=command.capitalize(), command=lambda key=command: run(key)).pack(
            side="left", padx=(0, 6)
        )

    append("Prueba «Mueve la pestaña VSCode a la mitad izquierda de la pantalla 1».\n")
    entry.focus_set()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
