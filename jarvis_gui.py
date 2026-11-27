import math
import sys
import tkinter as tk
from tkinter import ttk

from updater import VERSION

BG = "#060b17"
PANEL = "#0d172b"
EDGE = "#203956"
CYAN = "#52f0ff"
TEXT = "#e7f3ff"
MUTED = "#9aadc7"
FONT = "Segoe UI"


def create_panel(root, submit_command, check_update, packaged):
    root.title("JARVIS")
    root.geometry("980x640")
    root.minsize(650, 460)
    root.configure(bg=BG)
    root.columnconfigure(0, minsize=250)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(2, weight=1)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar", background=EDGE, troughcolor=PANEL,
                    bordercolor=PANEL, arrowcolor=CYAN, width=10)

    rail = tk.Frame(root, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
    rail.grid(row=0, column=0, rowspan=4, sticky="nsew", padx=(16, 12), pady=16)
    tk.Label(rail, text="J A R V I S", bg=PANEL, fg=TEXT, font=(FONT, 22, "bold")).pack(pady=(16, 0))
    core = tk.Canvas(rail, width=220, height=205, bg=PANEL, highlightthickness=0)
    core.pack()
    phase = 0
    animation = None

    def animate():
        nonlocal phase, animation
        animation = None
        if root.state() != "normal" and root.state() != "zoomed":
            return
        core.delete("all")
        x, y = 110, 100
        for radius, color in ((88, EDGE), (72, "#174861"), (51, "#21627b"), (36, "#3b315f")):
            core.create_oval(x-radius, y-radius, x+radius, y+radius, outline=color)
        for angle in range(0, 360, 10):
            radians = math.radians(angle)
            inner = 77 if angle % 30 == 0 else 81
            core.create_line(x+inner*math.cos(radians), y+inner*math.sin(radians),
                             x+85*math.cos(radians), y+85*math.sin(radians), fill="#2c5575")
        for radius, angle, length, color in ((88, phase, 65, CYAN), (72, -phase, 100, "#a580ff"),
                                             (51, phase*2, 75, CYAN)):
            core.create_arc(x-radius, y-radius, x+radius, y+radius, start=angle,
                            extent=length, style="arc", outline=color, width=3)
        glow = 19 + 4 * math.sin(math.radians(phase))
        core.create_oval(x-glow, y-glow, x+glow, y+glow, fill="#12394d", outline=CYAN)
        core.create_oval(x-5, y-5, x+5, y+5, fill=CYAN, outline="")
        phase = (phase + 3) % 360
        animation = root.after(65, animate)

    def mapped(event):
        if event.widget is root and animation is None:
            animate()

    def unmapped(event):
        nonlocal animation
        if event.widget is root and animation is not None:
            root.after_cancel(animation)
            animation = None

    root.bind("<Map>", mapped)
    root.bind("<Unmap>", unmapped)

    status = tk.StringVar(value="Listo")
    tk.Label(rail, textvariable=status, bg=PANEL, fg=CYAN, font=("Consolas", 10)).pack(pady=(0, 10))
    toolbar = tk.Frame(rail, bg=PANEL)
    toolbar.pack(fill="x", padx=12, pady=(0, 12))
    tk.Label(root, text="Control de escritorio", bg=BG, fg=TEXT, font=(FONT, 20, "bold")).grid(
        row=0, column=1, sticky="w", padx=(0, 16), pady=(20, 8)
    )

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
    panel.grid(row=2, column=1, sticky="nsew", padx=(0, 16))
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

    outstanding = 0

    def run(command):
        nonlocal outstanding
        if submit_command(command):
            outstanding += 1
            status.set("Procesando…")
            append(f"TÚ · {command}", "you")

    def reply(response):
        nonlocal outstanding
        append(response, "reply")
        outstanding -= 1
        if outstanding == 0:
            status.set("Listo")

    for command in ("aplicaciones", "ventanas", "pantallas", "ayuda"):
        button(toolbar, command.capitalize(), lambda key=command: run(key)).pack(fill="x", pady=3)

    if packaged:
        update_status = tk.StringVar(value=f"Versión {VERSION}")
        tk.Label(rail, textvariable=update_status, bg=PANEL, fg=MUTED,
                 font=(FONT, 9)).pack(side="bottom", pady=(4, 10))
        update_button = button(rail, "Buscar actualizaciones", check_update)
        update_button.pack(side="bottom", fill="x", padx=12)

    def update_controls(label, available, busy):
        update_status.set(label)
        update_button.configure(
            state="disabled" if busy else "normal",
            text="Actualizar y reiniciar" if available else "Buscar actualizaciones",
        )

    form = tk.Frame(root, bg=BG)
    form.grid(row=3, column=1, sticky="ew", padx=(0, 16), pady=(12, 18))
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
    append("Prueba «Chrome esquina superior derecha» o «cierra el Bloc de notas».", "hint")
    return Panel(entry, reply, update_controls)


class Panel:
    def __init__(self, entry, reply, update_controls):
        self.entry = entry
        self.reply = reply
        self.update_controls = update_controls

    def focus(self):
        self.entry.focus_set()


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 u 11 para controlar el escritorio.")
        return 1
    from resident import launch

    return launch(create_panel, background="--background" in sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
