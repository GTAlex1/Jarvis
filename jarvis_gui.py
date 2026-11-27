import math
from queue import Empty, Queue
from threading import Thread
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from jarvis import Desktop, execute, normalize
from updater import VERSION, install_update, latest_update

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

    def animate():
        nonlocal phase
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
        root.after(65, animate)

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

    pending = Queue()
    responses = Queue()
    outstanding = 0

    def work():
        while True:
            desktop_command = pending.get()
            try:
                response = execute(desktop, desktop_command)
            except OSError as error:
                response = f"No se pudo completar la orden: {error}"
            responses.put(response)

    def run(command):
        nonlocal outstanding
        if normalize(command) == "salir":
            root.destroy()
            return
        outstanding += 1
        status.set("Procesando…")
        pending.put(command)
        append(f"TÚ · {command}", "you")

    def poll_responses():
        nonlocal outstanding
        try:
            response = responses.get_nowait()
        except Empty:
            pass
        else:
            append(response, "reply")
            outstanding -= 1
            if outstanding == 0:
                status.set("Listo")
        root.after(60, poll_responses)

    for command in ("aplicaciones", "ventanas", "pantallas", "ayuda"):
        button(toolbar, command.capitalize(), lambda key=command: run(key)).pack(fill="x", pady=3)

    if getattr(sys, "frozen", False):
        available = None
        updates = Queue()
        update_status = tk.StringVar(value=f"Versión {VERSION}")

        def update_worker(installing):
            try:
                result = install_update(available) if installing else latest_update()
                updates.put((installing, result, None))
            except (OSError, ValueError, KeyError, TypeError) as error:
                updates.put((installing, None, error))

        def start_update(installing=False):
            update_button.configure(state="disabled")
            update_status.set("Descargando…" if installing else "Buscando…")
            Thread(target=update_worker, args=(installing,), daemon=True).start()

        def update_clicked():
            if available is None:
                start_update()
            elif messagebox.askyesno("JARVIS", f"¿Instalar {available[0]} y reiniciar JARVIS?", parent=root):
                start_update(installing=True)

        def poll_updates():
            nonlocal available
            try:
                installing, result, error = updates.get_nowait()
            except Empty:
                pass
            else:
                if installing and error is None:
                    root.destroy()
                    return
                if error is not None:
                    update_status.set("Error de actualización")
                    if installing:
                        messagebox.showerror("JARVIS", str(error), parent=root)
                else:
                    available = result
                    update_status.set(f"Disponible {available[0]}" if available else f"Versión {VERSION} · al día")
                update_button.configure(
                    state="normal", text="Actualizar y reiniciar" if available else "Buscar actualizaciones",
                )
            root.after(120, poll_updates)

        tk.Label(rail, textvariable=update_status, bg=PANEL, fg=MUTED,
                 font=(FONT, 9)).pack(side="bottom", pady=(4, 10))
        update_button = button(rail, "Buscar actualizaciones", update_clicked)
        update_button.pack(side="bottom", fill="x", padx=12)
        root.after(350, start_update)
        poll_updates()

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
    append("Prueba «abre VSCode» o «minimiza Chrome».", "hint")
    Thread(target=work, daemon=True).start()
    poll_responses()
    entry.focus_set()
    animate()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
