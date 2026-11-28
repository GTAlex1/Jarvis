"""Mantenimiento no destructivo del servidor dedicado Nexora."""
import discord
from setup_server import CATEGORIES, ROLES, STAFF, MESSAGES, unique

ICONS=["📌","🌐","🛠","🧪","⚡","💬","🎙","🔒"]
FORUMS={"sugerencias":"ideas","reporte-de-errores":"incidencias"}

async def maintain(guild,client):
    me=guild.me
    if not me or not me.guild_permissions.administrator:
        raise RuntimeError("Se requiere Administrador temporal.")
    roles={name:unique([r for r in guild.roles if not r.managed],name) for name in ROLES}
    if any(r is None or r >= me.top_role for r in roles.values()):
        raise RuntimeError("Faltan roles o están por encima del bot.")
    categories=[]
    for icon,(name,mode,access,texts,voices) in zip(ICONS,CATEGORIES):
        old=unique(guild.categories,name)
        new=unique(guild.categories,f"{icon}・{name}")
        if old and new: raise RuntimeError(f"Categorías duplicadas: {name}")
        if not (old or new): raise RuntimeError(f"Falta categoría: {name}")
        categories.append((old or new,icon,name,mode,access))
    # Mantener IDs, mensajes y permisos; no borrar canales.
    for category,icon,name,mode,access in categories:
        if category.name==name:
            await category.edit(name=f"{icon}・{name}",reason="Nexora mantenimiento")
        print(f"OK estética: {name}")
    # Orden relativo, sin elevar roles por encima del bot.
    positions=sorted(r.position for r in roles.values())
    await guild.edit_role_positions(positions=dict(zip(reversed(list(roles.values())),positions)),reason="Nexora jerarquía")
    for name,role in roles.items():
        await role.edit(colour=discord.Colour(ROLES[name]),hoist=name in ("Founder","Developer","Moderator","Zero Division","Nexora Insider"))
    await guild.edit(verification_level=discord.VerificationLevel.medium, explicit_content_filter=discord.ContentFilter.all_members,reason="Nexora seguridad")
    print("OK jerarquía y verificación")
    # Foros nuevos, conservar los canales originales y sus mensajes.
    development=categories[2][0]
    if "COMMUNITY" in guild.features:
        for original,name in FORUMS.items():
            forum=unique(development.channels,name)
            if forum is None:
                forum=await guild.create_forum(name,category=development,topic=f"Publica aquí: {original}. No incluyas información privada.",reason="Nexora foros")
            if not isinstance(forum,discord.ForumChannel):
                raise RuntimeError(f"Nombre de foro ocupado: {name}")
            print(f"OK foro: {name}")
    else:
        print("PENDIENTE foros: habilita Comunidad manualmente y repite mantenimiento.")
    # Añadir embeds sin borrar los mensajes iniciales.
    for category,icon,name,mode,access in categories:
        for channel in category.text_channels:
            if channel.name not in MESSAGES: continue
            marker=f"Nexora · {channel.name} · v2"
            exists=False
            async for msg in channel.history(limit=None):
                if msg.author.id==client.user.id and any(e.footer.text==marker for e in msg.embeds):
                    exists=True
                    break
            if not exists:
                embed=discord.Embed(title=channel.name.replace("-"," ").title(),description=MESSAGES[channel.name],colour=0x22d3ee)
                embed.set_footer(text=marker)
                await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
            print(f"OK mensaje: {channel.name}")
    # AutoMod: limitar menciones masivas sin bloquear palabras normales.
    rules=await guild.fetch_automod_rules()
    name="Nexora · Protección de menciones"
    rule=unique(rules,name)
    if rule is None:
        await guild.create_automod_rule(name=name,event_type=discord.AutoModRuleEventType.message_send,trigger=discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.mention_spam,mention_limit=5),actions=[discord.AutoModRuleAction(custom_message="Evita las menciones masivas.")],enabled=True,reason="Nexora AutoMod")
    else:
        print("AutoMod existente: se conserva; comprueba que esté activo.")
    print("OK AutoMod de menciones")
    await audit(guild,client)
    print("PENDIENTE: retirar Administrador, revisar roles con Discord y limpiar canales iniciales manualmente.")

async def audit(guild,client):
    roles={name:unique([r for r in guild.roles if not r.managed],name) for name in ROLES}
    issues=0
    for icon,(name,mode,access,texts,voices) in zip(ICONS,CATEGORIES):
        category=unique(guild.categories,f"{icon}・{name}") or unique(guild.categories,name)
        if category is None:
            print(f"REVISAR categoría ausente: {name}")
            issues+=1
            continue
        if mode=="private":
            for channel in [category]+list(category.channels):
                if channel.permissions_for(guild.default_role).view_channel:
                    print(f"REVISAR acceso @everyone: {channel.name}")
                    issues+=1
                for role_name,role in roles.items():
                    if role is None: continue
                    expected=role_name in access
                    if channel.permissions_for(role).view_channel != expected:
                        print(f"REVISAR {channel.name}: {role_name}")
                        issues+=1
                if any(isinstance(target,discord.Member) and target.id!=client.user.id and overwrite.view_channel is True for target,overwrite in channel.overwrites.items()):
                    print(f"REVISAR acceso individual: {channel.name}")
                    issues+=1
    print(f"Auditoría básica: {issues} incidencias. No sustituye la prueba con miembros reales y roles combinados.")
