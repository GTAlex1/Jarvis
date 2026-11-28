"""Interfaz local de Nexora Server Builder."""
import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import discord
from setup_server import CATEGORIES, ROLES, MESSAGES, configure
import contextlib
from maintenance import maintain, audit
from permissions_v3 import permissions, finalize
from community_v4 import community, identity

BG="#0b1020"
PANEL="#151d32"
FG="#e8efff"
ACC="#67e8f9"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nexora | Server Builder 4.0")
        self.geometry("860x690")
        self.minsize(680,560)
        self.configure(bg=BG)
        self.events=queue.Queue()
        self.busy=False
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.guild=tk.StringVar(value="1576054535812554773")
        self.token=tk.StringVar()
        self.status=tk.StringVar(value="Preparado · Sin conexión")
        style=ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton",background="#263b62",foreground=FG,padding=10)
        style.map("TButton",background=[("active","#36568a"),("disabled","#303746")])
        style.configure("TEntry",fieldbackground=PANEL,foreground=FG,insertcolor=FG,padding=8)
        style.configure("Horizontal.TProgressbar",background=ACC,troughcolor=PANEL)
        body=tk.Frame(self,bg=BG,padx=24,pady=20)
        body.pack(fill="both",expand=True)
        tk.Label(body,text="N E X O R A",font=("Segoe UI",24,"bold"),bg=BG,fg=ACC).pack(anchor="w")
        tk.Label(body,text="SERVER BUILDER  /  Configuración de Discord",bg=BG,fg=FG,font=("Segoe UI",12)).pack(anchor="w",pady=(0,18))
        for label,var,secret in [("ID del servidor",self.guild,False),("Token del bot · no se guarda",self.token,True)]:
            tk.Label(body,text=label,bg=BG,fg=FG).pack(anchor="w")
            ttk.Entry(body,textvariable=var,show="*" if secret else "").pack(fill="x",pady=(4,10))
        bar=tk.Frame(body,bg=BG)
        bar.pack(fill="x",pady=8)
        self.preview=ttk.Button(bar,text="Simular estructura",command=self.simulate)
        self.preview.pack(side="left",padx=(0,8))
        self.apply=ttk.Button(bar,text="Generar servidor",command=self.start)
        self.apply.pack(side="left",padx=(0,8))
        self.maintenance=ttk.Button(bar,text="Personalizar",command=lambda:self.start("maintenance"))
        self.maintenance.pack(side="left",padx=(0,8))
        self.audit=ttk.Button(bar,text="Auditar",command=lambda:self.start("audit"))
        self.audit.pack(side="left")
        extra=tk.Frame(body,bg=BG)
        extra.pack(fill="x",pady=4)
        self.perms=ttk.Button(extra,text="Configurar permisos v3",command=lambda:self.start("permissions"))
        self.perms.pack(side="left",padx=(0,8))
        self.finish=ttk.Button(extra,text="Retirar Administrador",command=lambda:self.start("finalize"))
        self.finish.pack(side="left")
        third=tk.Frame(body,bg=BG)
        third.pack(fill="x",pady=4)
        self.community=ttk.Button(third,text="Configurar incorporación",command=lambda:self.start("community"))
        self.community.pack(side="left",padx=(0,8))
        self.identity=ttk.Button(third,text="Importar Identity Pack",command=lambda:self.start("identity"))
        self.identity.pack(side="left")
        self.progress=ttk.Progressbar(body,mode="indeterminate")
        self.progress.pack(fill="x",pady=8)
        tk.Label(body,textvariable=self.status,bg=BG,fg=ACC).pack(anchor="w")
        self.log=tk.Text(body,bg=PANEL,fg=FG,insertbackground=FG,relief="flat",wrap="word",font=("Consolas",10),state="disabled")
        self.log.pack(fill="both",expand=True,pady=8)
        self.after(100,self.poll)
        self.simulate()
    def write(self,s):
        self.log.configure(state="normal")
        self.log.insert("end",s+"\n")
        self.log.see("end")
        self.log.configure(state="disabled")
    def simulate(self):
        self.write("SIMULACIÓN LOCAL · Sin cambios en Discord")
        for name,mode,access,texts,voices in CATEGORIES:
            self.write(f"{name} [{mode}]")
            self.write("  "+", ".join(texts.split()+[v for v in voices.split("|") if v]))
        self.write(f"{len(ROLES)} roles · {len(MESSAGES)} mensajes iniciales")
    def start(self,mode="generate"):
        raw=self.guild.get().strip()
        token=self.token.get().strip()
        if not raw.isascii() or not raw.isdigit() or not token:
            messagebox.showerror("Datos necesarios","Introduce un ID numérico y el token del bot.")
            return
        if mode=="finalize" and not messagebox.askyesno("Finalizar","¿Has revisado los permisos y terminado todas las operaciones? El bot perderá Administrador."): return
        if mode!="audit" and not messagebox.askyesno("Confirmar",f"Operación {mode} en Nexora {raw}. Puede modificar configuración y permisos. Usa solo un servidor dedicado."):
            return
        self.token.set("")
        self.busy=True
        self.apply.state(["disabled"])
        self.preview.state(["disabled"])
        self.maintenance.state(["disabled"])
        self.audit.state(["disabled"])
        self.perms.state(["disabled"])
        self.finish.state(["disabled"])
        self.community.state(["disabled"])
        self.identity.state(["disabled"])
        self.progress.start(12)
        self.status.set("Conectando a Discord...")
        threading.Thread(target=self.worker,args=(int(raw),token,mode),daemon=True).start()
    def worker(self,guild_id,token,mode):
        app=self
        class Sink:
            def write(self,s):
                if s.strip():
                    app.events.put(("log",s.rstrip().replace(token,"[oculto]")))
                return len(s)
            def flush(self): pass
        async def run():
            client=discord.Client(intents=discord.Intents(guilds=True))
            done=False
            errors=[]
            @client.event
            async def on_ready():
                nonlocal done
                if done: return
                done=True
                try:
                    guild=client.get_guild(guild_id)
                    if guild is None or guild.name!="Nexora":
                        raise RuntimeError("No se encuentra el servidor Nexora indicado.")
                    app.events.put(("log",f"Conectado a {guild.name} ({guild.id})"))
                    with contextlib.redirect_stdout(Sink()):
                        await {"generate":configure,"maintenance":maintain,"audit":audit,"permissions":permissions,"finalize":finalize,"community":community,"identity":identity}[mode](guild,client)
                except Exception as exc:
                    errors.append(exc)
                finally:
                    await client.close()
            async with client:
                await asyncio.wait_for(client.start(token),timeout=900)
            if errors: raise errors[0]
            if not done: raise RuntimeError("Conexión finalizada antes de configurar.")
        try:
            asyncio.run(run())
            self.events.put(("done","Operación terminada · Consulta el registro"))
        except Exception as exc:
            self.events.put(("log",f"ERROR: {type(exc).__name__}: {str(exc).replace(token,'[oculto]')}"))
            self.events.put(("done","Error · Puede haber cambios parciales"))
    def poll(self):
        while True:
            try: kind,msg=self.events.get_nowait()
            except queue.Empty: break
            self.write(msg)
            if kind=="done":
                self.busy=False
                self.progress.stop()
                self.apply.state(["!disabled"])
                self.preview.state(["!disabled"])
                self.maintenance.state(["!disabled"])
                self.audit.state(["!disabled"])
                self.perms.state(["!disabled"])
                self.finish.state(["!disabled"])
                self.community.state(["!disabled"])
                self.identity.state(["!disabled"])
                self.status.set(msg)
        self.after(100,self.poll)
    def close(self):
        if self.busy:
            messagebox.showinfo("Operación activa","Espera a que termine la configuración.")
            return
        self.destroy()

if __name__=="__main__":
    App().mainloop()
