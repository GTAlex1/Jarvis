"""Configurador local de Nexora. Python 3.10+, discord.py 2.x.
Sin --apply solo muestra el plan. No elimina recursos ni invita usuarios.
"""
import argparse
import asyncio
import getpass
import os
import discord

ROLES = {
    "Founder": 0xef4444, "Developer": 0xa855f7, "Moderator": 0x22c55e,
    "Zero Division": 0xeab308, "Nexora Insider": 0x38bdf8,
    "Early Adopter": 0x14b8a6, "Member": 0x94a3b8, "Nexora": 0x818cf8,
}
STAFF = ("Founder", "Developer", "Moderator")
CATEGORIES = [
    ("INFORMACIÓN", "read", (), "bienvenida normas anuncios roadmap descargas changelog enlaces-oficiales", ""),
    ("COMUNIDAD", "public", (), "general presentaciones off-topic gaming memes", ""),
    ("DESARROLLO", "public", (), "sugerencias votaciones reporte-de-errores estado-del-proyecto github", ""),
    ("NEXORA INSIDER", "private", STAFF + ("Zero Division", "Nexora Insider"), "insider-general versiones-experimentales pruebas feedback diagnósticos", "Laboratorio Nexora"),
    ("ZERO DIVISION", "private", STAFF + ("Zero Division",), "zero-general laboratorio propuestas", ""),
    ("SOPORTE", "public", (), "ayuda preguntas-frecuentes tickets", ""),
    ("CANALES DE VOZ", "public", (), "", "General|Gaming 1|Gaming 2|Gaming 3|AFK"),
    ("ADMINISTRACIÓN", "private", STAFF, "administración moderación registro-de-incidencias planificación configuración-bots", "Reuniones de desarrollo"),
]
MESSAGES = {
    "bienvenida": "**Bienvenido a Nexora**\nOne intelligence. Every device.\nJARVIS evoluciona hacia un asistente personal inteligente. Actualmente está en validación interna.",
    "normas": "**Normas**\nRespeta a los demás. No acoso, spam, estafas, malware ni difusión de datos privados. Usa los canales adecuados. Se permite humor informal sin acoso. Respeta las normas de Discord y la confidencialidad de las pruebas.",
    "roadmap": "**Hoja de ruta**\n1.0: asistente personal. 2.0: ecosistema conectado. 3.0: inteligencia social. Son objetivos, no funciones disponibles ni fechas garantizadas.\nhttps://github.com/GTAlex1/Jarvis/blob/main/ROADMAP.md",
    "descargas": "Versiones de validación interna; no se ha autorizado todavía la distribución a betatesters externos.\nhttps://github.com/GTAlex1/Jarvis/releases",
    "enlaces-oficiales": "https://github.com/GTAlex1/Jarvis",
    "changelog": "Consulta las notas de cada versión: https://github.com/GTAlex1/Jarvis/releases",
    "reporte-de-errores": "**Plantilla**\nVersión, SO, descripción, pasos, resultado esperado y real, frecuencia, diagnóstico opcional. No compartas tokens, contraseñas, audio privado ni firmas biométricas.",
    "sugerencias": "**Plantilla**\nNombre, descripción, problema que resuelve, funcionamiento esperado e información adicional.",
    "tickets": "No publiques datos privados aquí. El sistema de tickets privados todavía no está disponible.",
}

def unique(items, name):
    found = [x for x in items if x.name == name]
    if len(found) > 1:
        raise RuntimeError(f"Nombre ambiguo: {name}")
    return found[0] if found else None

async def configure(guild, client):
    me = guild.me
    if me is None or not me.guild_permissions.administrator:
        raise RuntimeError("Para esta configuración inicial, autoriza temporalmente Administrador al bot. Retíralo al terminar.")
    # Conservar categorías ajenas al plan, incluidas las predeterminadas.
    allowed = {c[0] for c in CATEGORIES}
    for c in guild.categories:
        if c.name not in allowed:
            print(f"Se conserva categoría existente: {c.name}")
    roles = {}
    for name, color in ROLES.items():
        role = unique([r for r in guild.roles if not r.managed], name)
        if name == "Nexora" and role is None:
            role = unique([r for r in guild.roles if not r.managed], "Nexora AI")
        if role is None:
            role = await guild.create_role(name=name, colour=discord.Colour(color),
                                           permissions=discord.Permissions.none(), reason="Nexora setup")
        elif role.managed or role >= me.top_role or (role.permissions.value and name != "Moderator"):
            raise RuntimeError(f"Rol existente no seguro para reutilizar: {name}")
        roles[name] = role
    owner = await guild.fetch_member(guild.owner_id)
    if roles["Founder"] not in owner.roles:
        await owner.add_roles(roles["Founder"], reason="Nexora setup")
    # Denegar invitaciones y menciones masivas en los canales gestionados.
    for name, mode, access, texts, voices in CATEGORIES:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=mode != "private", send_messages=mode == "public",
                connect=mode == "public", create_instant_invite=False,
                mention_everyone=False, create_public_threads=False,
                create_private_threads=False, send_messages_in_threads=False),
            me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                            read_message_history=True, manage_channels=True),
        }
        for role_name in access:
            overwrites[roles[role_name]] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, connect=True, read_message_history=True)
        if name in ("DESARROLLO", "NEXORA INSIDER"):
            previous = unique(guild.categories, name)
            if previous is None:
                previous = next((c for c in guild.categories if c.name.endswith("・"+name)),None)
            if previous and previous.overwrites_for(roles["Developer"]).manage_messages:
                dev_overwrite = overwrites.get(roles["Developer"], discord.PermissionOverwrite())
                dev_overwrite.manage_messages = True
                dev_overwrite.manage_threads = True
                overwrites[roles["Developer"]] = dev_overwrite
        if mode == "read":
            for role_name in STAFF:
                overwrites[roles[role_name]] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True)
        icon = ["📌","🌐","🛠","🧪","⚡","💬","🎙","🔒"][next(i for i,c in enumerate(CATEGORIES) if c[0]==name)]
        category = unique(guild.categories, name) or unique(guild.categories, f"{icon}・{name}")
        if category is None:
            category = await guild.create_category(name, overwrites=overwrites)
        else:
            await category.edit(overwrites=overwrites)
        for channel_name, kind in [(n, "text") for n in texts.split()] + [(n, "voice") for n in voices.split("|") if n]:
            channel = unique(category.channels, channel_name)
            if channel is None:
                create = category.create_text_channel if kind == "text" else category.create_voice_channel
                channel = await create(channel_name)
            else:
                expected = discord.TextChannel if kind == "text" else discord.VoiceChannel
                if not isinstance(channel, expected):
                    raise RuntimeError(f"Tipo inesperado: {channel_name}")
            await channel.edit(sync_permissions=True)
            if kind == "text" and channel_name in MESSAGES:
                message = MESSAGES[channel_name]
                # Buscar mensajes propios previos para evitar duplicados.
                exists = False
                async for old in channel.history(limit=None):
                    if old.author.id == client.user.id and old.content == message:
                        exists = True
                        break
                if not exists:
                    await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
            print(f"OK {name}/{channel_name}")
    print(f"Configuración aplicada: https://discord.com/channels/{guild.id}")
    print("Revisa permisos con Ver servidor como rol. Retira Administrador al bot o expúlsalo.")
    print("Pendiente manual: AutoMod, verificación, jerarquía visual, foros, moderación y tickets.")

async def run(args):
    token = os.environ.get("NEXORA_DISCORD_TOKEN") or getpass.getpass("Token del BOT (oculto): ")
    client = discord.Client(intents=discord.Intents.none())
    async with client:
        await client.login(token)
        guild = await client.fetch_guild(args.guild)
        print(f"Destino: {guild.name} ({guild.id})")
        if guild.name != "Nexora":
            raise RuntimeError("El servidor debe llamarse exactamente Nexora.")
        if input("Escribe el ID del servidor para confirmar: ").strip() != str(guild.id):
            raise RuntimeError("Confirmación incorrecta")
        # fetch_guild no incluye canales ni miembro propio en caché.
        # Conectar gateway con intent de guilds para obtenerlos.
    client = discord.Client(intents=discord.Intents(guilds=True))
    done = asyncio.Event()
    error = []
    @client.event
    async def on_ready():
        if done.is_set():
            return
        done.set()
        try:
            guild = client.get_guild(args.guild)
            if guild is None or guild.name != "Nexora":
                raise RuntimeError("Servidor no disponible")
            await configure(guild, client)
        except Exception as exc:
            error.append(exc)
        finally:
            await client.close()
    await client.start(token)
    if error:
        raise error[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guild", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        for name, mode, access, texts, voices in CATEGORIES:
            print(name, mode, access, texts, voices)
        print("Simulación: no se ha conectado a Discord.")
        return
    if not args.guild:
        parser.error("--apply requiere --guild ID")
    asyncio.run(run(args))

if __name__ == "__main__":
    main()
