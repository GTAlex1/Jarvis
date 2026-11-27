import math
import sys
import tkinter as tk
from tkinter import ttk

from jarvis import Desktop, execute, normalize

BG = "#060b17"
PANEL = "#0d172b"
EDGE = "#203956"
CYAN = "#52f0ff"
TEXT = "#e7f3ff"
MUTED = "#9aadc7"
FONT = "Segoe UI"


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 u 11 para controlar el escritorio.")
        return 1

    desktop = Desktop()
    root = tk.Tk()
    root.title("JARVIS")
    root.geometry("850x580")
    root.minsize(540, 420)
    root.configure(bg=BG)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(2, weight=1)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar", background=EDGE, troughcolor=PANEL,
                    bordercolor=PANEL, arrowcolor=CYAN, width=10)

    header = tk.Canvas(root, height=126, bg=BG, highlightthickness=0)
    header.grid(row=0, column=0, sticky="ew")
    phase = 0

    def animate():
        nonlocal phase
        width = header.winfo_width()
        header.delete("all")
        for x in range(0, width, 24):
            header.create_line(x, 0, x, 126, fill="#101b31")
        for y in range(6, 126, 24):
            header.create_line(0, y, width, y, fill="#101b31")
        center = width - 80
        for radius, color in ((46, EDGE), (38, "#174861"), (23, "#21627b")):
            header.create_oval(center-radius, 63-radius, center+radius, 63+radius, outline=color)
        for radius, angle, length, color in ((46, phase, 80, CYAN), (38, -phase, 105, "#9478ff")):
            header.create_arc(center-radius, 63-radius, center+radius, 63+radius,
                              start=angle, extent=length, style="arc", outline=color, width=2)
        glow = int(19 + 4 * math.sin(math.radians(phase)))
        header.create_oval(center-glow, 63-glow, center+glow, 63+glow, fill="#12394d", outline=CYAN)
        header.create_oval(center-5, 58, center+5, 68, fill=CYAN, outline="")
        header.create_text(26, 39, text="J A R V I S", anchor="w", fill=TEXT, font=(FONT, 28, "bold"))
        header.create_text(28, 83, text="Control de escritorio", anchor="w", fill=MUTED, font=(FONT, 11))
        phase = (phase + 4) % 360
        root.after(70, animate)

    toolbar = tk.Frame(root, bg=BG)
    toolbar.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

    def button(parent, text, action, primary=False):
        control = tk.Button(
            parent, text=text, command=action, relief="flat", borderwidth=0, padx=14, pady=6,
            bg=CYAN if primary else PANEL, fg=BG if primary else TEXT,
            activebackground="#a6fcff" if primary else EDGE, activeforeground=BG if primary else CYAN,
            highlightbackground=EDGE, highlightcolor=CYAN, highlightthickness=1,
            font=(FONT, 10, "bold"), cursor="hand2",
        )
        control.bind("<Return>", lambda _event: control.invoke())
        return control

    panel = tk.Frame(root, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
    panel.grid(row=2, column=0, sticky="nsew", padx=22)
    panel.columnconfigure(0, weight=1)
    panel.rowconfigure(1, weight=1)
    tk.Label(panel, text="Historial", bg=PANEL, fg=CYAN, font=(FONT, 10, "bold")).grid(
        row=0, column=0, sticky="w", padx=14, pady=(9, 0)
    )
    history = tk.Text(
        panel, wrap="word", bg=PANEL, fg=TEXT, relief="flat", padx=14, pady=10,
        font=(FONT, 11), state="disabled", cursor="arrow", selectbackground=EDGE,
    )
    scrollbar = ttk.Scrollbar(panel, orient="vertical", command=history.yview)
    history.configure(yscrollcommand=scrollbar.set)
    history.grid(row=1, column=0, sticky="nsew")
    scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 5), pady=6)
    history.tag_configure("you", foreground=CYAN, spacing1=7)
    history.tag_configure("reply", foreground=TEXT, spacing3=7)
    history.tag_configure("hint", foreground=MUTED)

    def append(message, tag):
        history.configure(state="normal")
        history.insert("end", message + "\n", tag)
        history.configure(state="disabled")
        history.see("end")

    def run(command):
        if normalize(command) == "salir":
            root.destroy()
            return
        append(f"TÚ · {command}", "you")
        try:
            response = execute(desktop, command)
        except OSError as error:
            response = f"No se pudo completar la orden: {error}"
        append(response, "reply")

    for command in ("pantallas", "ventanas", "ayuda"):
        button(toolbar, command.capitalize(), lambda key=command: run(key)).pack(side="left", padx=(0, 8))

    form = tk.Frame(root, bg=BG)
    form.grid(row=3, column=0, sticky="ew", padx=22, pady=(12, 18))
    form.columnconfigure(0, weight=1)
    tk.Label(form, text="Escribe una orden", bg=BG, fg=MUTED, font=(FONT, 10)).grid(
        row=0, column=0, sticky="w", pady=(0, 4)
    )
    entry = tk.Entry(
        form, bg=PANEL, fg=TEXT, insertbackground=CYAN, selectbackground=EDGE,
        relief="flat", highlightbackground=EDGE, highlightcolor=CYAN,
        highlightthickness=1, font=(FONT, 12),
    )
    entry.grid(row=1, column=0, sticky="ew", ipady=7)

    def submit(_event=None):
        command = entry.get().strip()
        if command:
            entry.delete(0, "end")
            entry.focus_set()
            run(command)
        return "break"

    button(form, "Enviar  ↵", submit, primary=True).grid(row=1, column=1, padx=(10, 0), sticky="ns")
    entry.bind("<Return>", submit)
    append("Prueba «VSCode izquierda» o «Chrome pantalla completa».", "hint")
    entry.focus_set()
    animate()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
