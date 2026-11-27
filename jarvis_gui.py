import math
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from preferences import CAPTURE_INTERFACES, VoiceSettings
from updater import VERSION
from voice_service import STATE_LABELS

BG = "#060b17"
PANEL = "#0d172b"
EDGE = "#203956"
CYAN = "#52f0ff"
TEXT = "#e7f3ff"
MUTED = "#9aadc7"
FONT = "Segoe UI"


def create_panel(root, submit_command, check_update, packaged, open_voice_settings):
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
    tk.Label(rail, textvariable=status, bg=PANEL, fg=CYAN, font=("Consolas", 10)).pack()
    voice_indicator = tk.Label(rail, bg=PANEL, fg=MUTED, wraplength=222, font=(FONT, 9))
    voice_indicator.pack(pady=(4, 10), padx=12)
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

    button(toolbar, "Ajustes de voz", open_voice_settings).pack(fill="x", pady=3)

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
    return Panel(root, entry, reply, append, update_controls, voice_indicator)


class Panel:
    def __init__(self, root, entry, reply, append, update_controls, voice_indicator):
        self.root = root
        self.entry = entry
        self.reply = reply
        self.voice_message = append
        self.update_controls = update_controls
        self.indicator = voice_indicator
        self.voice_dialog = None

    def focus(self):
        self.entry.focus_set()

    def voice_status(self, state, detail):
        colors = {"listening": "#73ffc1", "processing": "#ffd37a", "executing": "#ffd37a",
                  "unavailable": "#ffadad", "disabled": MUTED, "muted": MUTED}
        text = f"● {STATE_LABELS[state]}"
        if detail:
            text += f"\n{detail}"
        self.indicator.configure(text=text, fg=colors.get(state, CYAN))

    def open_voice_settings(self, settings, save, refresh, test, cancel_test, meter, progress):
        if self.voice_dialog is not None and self.voice_dialog.window.winfo_exists():
            self.voice_dialog.window.lift()
            return
        self.voice_dialog = VoiceDialog(self.root, settings, save, refresh, test, cancel_test, meter, progress)

    def voice_catalog(self, *catalog):
        if self.voice_dialog is not None and self.voice_dialog.window.winfo_exists():
            self.voice_dialog.show_catalog(*catalog)


    def voice_test(self, result):
        if self.voice_dialog is not None and self.voice_dialog.window.winfo_exists():
            self.voice_dialog.test_result(result)


class VoiceDialog:
    def __init__(self, parent, settings, save, refresh, test, cancel_test, meter, progress):
        self.window = window = tk.Toplevel(parent, bg=BG, padx=20, pady=16)
        window.title("JARVIS · Ajustes de voz")
        window.transient(parent)
        window.resizable(False, False)
        window.columnconfigure(1, weight=1)
        self.save = save
        self.refresh = refresh
        self.test = test
        self.cancel_test = cancel_test
        self.meter = meter
        self.progress = progress
        self.inputs = None
        self.meter_job = None
        window.bind("<Map>", self.mapped)
        window.bind("<Unmap>", self.unmapped)
        window.bind("<Destroy>", self.destroyed)
        self.enabled = tk.BooleanVar(window, settings.enabled)
        self.volume = tk.IntVar(window, settings.volume)
        self.sensitivity = tk.IntVar(window, settings.sensitivity)
        self.conversational = tk.BooleanVar(window, settings.conversational)
        self.context_seconds = tk.StringVar(window, str(settings.context_seconds))
        self.reply_seconds = tk.StringVar(window, str(settings.reply_seconds))
        box = tk.Checkbutton(
            window, text="Escucha permanente", variable=self.enabled, bg=BG, fg=TEXT,
            activebackground=BG, activeforeground=CYAN, selectcolor=PANEL, font=(FONT, 11, "bold"),
        )
        box.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.microphone = self.combobox("Micrófono", 1)
        self.microphone.bind("<<ComboboxSelected>>", lambda _event: self.update_interfaces())
        self.interface = self.combobox("Interfaz de captura", 2)
        self.interface.configure(values=("Automática",))
        self.set_interface(settings.interface)
        self.speaker = self.combobox("Voz de respuesta", 3)
        self.slider("Volumen", self.volume, 0, 100, 4)
        self.slider("Sensibilidad", self.sensitivity, 1, 5, 5)

        tk.Checkbutton(
            window, text="Modo conversacional", variable=self.conversational, bg=BG, fg=TEXT,
            activebackground=BG, activeforeground=CYAN, selectcolor=PANEL, font=(FONT, 10),
        ).grid(row=6, column=0, columnspan=2, sticky="w")
        self.seconds("Contexto (segundos)", self.context_seconds, 5, 120, 7)
        self.seconds("Espera de respuesta (segundos)", self.reply_seconds, 3, 18, 8)
        self.detail = self.combobox("Detalle hablado", 9)
        self.detail.configure(values=("Breve", "Normal", "Ampliado"))
        self.detail.set(settings.speech_detail.capitalize())
        self.speaker_threshold = tk.StringVar(window, str(settings.speaker_threshold))
        self.seconds("Exigencia de voz (65–90)", self.speaker_threshold, 65, 90, 10)
        self.label("Nivel del micrófono", 11)
        self.level = ttk.Progressbar(window, maximum=100, mode="determinate")
        self.level.grid(row=11, column=1, sticky="ew", pady=4)
        self.input_route = tk.Label(window, bg=BG, fg=MUTED, wraplength=420, justify="left")
        self.input_route.grid(row=12, column=0, columnspan=2, sticky="w")
        self.test_status = tk.Label(window, bg=BG, fg=MUTED, wraplength=420, justify="left")
        self.test_status.grid(row=13, column=0, columnspan=2, sticky="w")
        self.transcription = tk.Label(window, bg=BG, fg=CYAN, wraplength=420, justify="left")
        self.transcription.grid(row=14, column=0, columnspan=2, sticky="w")
        self.notice = tk.Label(window, bg=BG, fg=MUTED, wraplength=420, justify="left")
        self.notice.grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 4))
        controls = tk.Frame(window, bg=BG)
        controls.grid(row=16, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.reload = ttk.Button(controls, text="Actualizar lista", command=self.load)
        self.reload.pack(side="left")
        self.test_button = ttk.Button(controls, text="Probar micrófono", command=self.start_test)
        self.test_button.pack(side="left", padx=8)
        ttk.Button(controls, text="Guardar", command=self.commit).pack(side="right")
        ttk.Button(controls, text="Cancelar", command=window.destroy).pack(side="right", padx=8)

        self.microphones = self.populate(self.microphone, "Predeterminado de Windows", [], settings.device)
        self.speakers = self.populate(self.speaker, "Automática (prioriza español)", [], settings.voice)
        self.load()

    def mapped(self, event):
        if event.widget is self.window and self.meter_job is None:
            self.update_meter()

    def unmapped(self, event):
        if event.widget is self.window and self.meter_job is not None:
            self.window.after_cancel(self.meter_job)
            self.meter_job = None

    def update_meter(self):
        value, route = self.meter()
        self.level.configure(value=value)
        self.input_route.configure(text=route)
        reading = self.progress()
        self.test_status.configure(text=reading.status() if reading else "")
        self.transcription.configure(text=reading.text if reading else "")
        self.meter_job = self.window.after(100, self.update_meter)

    def destroyed(self, event):
        self.unmapped(event)
        if event.widget is self.window:
            self.cancel_test()

    def start_test(self):
        self.test_button.configure(state="disabled")
        self.reload.configure(state="disabled")
        self.notice.configure(text="Di «abre Spotify» al empezar cada prueba de captura…")
        self.test(self.microphones[self.microphone.get()], CAPTURE_INTERFACES[self.interface.get()])

    def test_result(self, result):
        self.notice.configure(text=result)
        self.test_button.configure(state="normal")
        self.reload.configure(state="normal")

    def combobox(self, label, row):
        self.label(label, row)
        box = ttk.Combobox(self.window, state="readonly", width=40)
        box.grid(row=row, column=1, sticky="ew", pady=4)
        return box

    def label(self, text, row):
        tk.Label(self.window, text=text, bg=BG, fg=TEXT, font=(FONT, 10)).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=4,
        )

    def slider(self, label, variable, first, last, row):
        self.label(label, row)
        tk.Scale(
            self.window, from_=first, to=last, variable=variable, orient="horizontal",
            bg=BG, fg=CYAN, troughcolor=PANEL, highlightthickness=0, activebackground=EDGE,
        ).grid(row=row, column=1, sticky="ew")

    def seconds(self, label, variable, first, last, row):
        self.label(label, row)
        ttk.Spinbox(self.window, from_=first, to=last, width=6, textvariable=variable).grid(
            row=row, column=1, sticky="w", pady=3,
        )

    @staticmethod
    def populate(box, automatic, entries, selected):
        options = {automatic: "", **dict(entries)}
        if selected and selected not in options.values():
            options[f"{selected} (no disponible)"] = selected
        box.configure(values=tuple(options))
        box.set(next(label for label, value in options.items() if value == selected))
        return options

    def set_interface(self, interface):
        self.interface.set(next(label for label, value in CAPTURE_INTERFACES.items() if value == interface))

    def update_interfaces(self):
        selection = self.microphones[self.microphone.get()]
        available = self.inputs.interfaces_for(selection) if self.inputs else set()
        options = tuple(label for label, api in CAPTURE_INTERFACES.items() if not api or api in available)
        self.interface.configure(values=options)
        if self.interface.get() not in options:
            self.interface.set("Automática")
            self.notice.configure(text="La interfaz anterior no está disponible para este micrófono.")

    def load(self):
        self.reload.configure(state="disabled")
        self.test_button.configure(state="disabled")
        self.notice.configure(text="Buscando micrófonos y voces de Windows…")
        self.refresh()

    def show_catalog(self, devices, voices, error):
        self.inputs = devices
        self.notice.configure(text=error)
        if devices is not None:
            selection, interface = devices.migrate(
                self.microphones[self.microphone.get()], CAPTURE_INTERFACES[self.interface.get()],
            )
            self.set_interface(interface)
            self.microphones = self.populate(
                self.microphone, "Predeterminado de Windows",
                ((item.label, item.key) for item in devices.devices), selection,
            )
        self.speakers = self.populate(
            self.speaker, "Automática (prioriza español)", ((f"{name} ({lang})", name) for name, lang in voices),
            self.speakers[self.speaker.get()],
        )
        self.update_interfaces()
        self.reload.configure(state="normal")
        self.test_button.configure(state="normal")

    def commit(self):
        try:
            self.save(VoiceSettings(
                enabled=self.enabled.get(), device=self.microphones[self.microphone.get()],
                voice=self.speakers[self.speaker.get()], volume=self.volume.get(),
                sensitivity=self.sensitivity.get(), interface=CAPTURE_INTERFACES[self.interface.get()],
                conversational=self.conversational.get(), context_seconds=int(self.context_seconds.get()),
                reply_seconds=int(self.reply_seconds.get()), speech_detail=self.detail.get().lower(),
                speaker_threshold=int(self.speaker_threshold.get()),
            ))
        except (OSError, ValueError) as error:
            messagebox.showerror("JARVIS", str(error), parent=self.window)
        else:
            self.window.destroy()


def main():
    if sys.platform != "win32":
        print("JARVIS necesita Windows 10 u 11 para controlar el escritorio.")
        return 1
    if len(sys.argv) == 4 and sys.argv[1] == "--diagnostico-voz":
        from voice_probe import report

        return report(sys.argv[2], sys.argv[3])
    from resident import launch

    return launch(create_panel, background="--background" in sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
