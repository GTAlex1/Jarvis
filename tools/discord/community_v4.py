"""Community configuration and non-destructive asset import."""
import base64
import json
from pathlib import Path
import discord
from discord.http import Route

ROOT=Path(__file__).resolve().parent/"assets"

def channel(guild,name):
    matches=[c for c in guild.text_channels if c.name==name and c.category and "・" in c.category.name]
    if len(matches)!=1: raise RuntimeError(f"Canal no identificado de forma única: {name}")
    return matches[0]

async def community(guild,client):
    if "COMMUNITY" not in guild.features:
        raise RuntimeError("Activa Comunidad primero.")
    if not guild.me.guild_permissions.administrator:
        raise RuntimeError("Se requiere Administrador temporal.")
    names=["bienvenida","normas","anuncios","roadmap","general","gaming","ayuda","memes","presentaciones"]
    defaults=[channel(guild,n) for n in names]
    if sum(c.permissions_for(guild.default_role).view_channel and c.permissions_for(guild.default_role).send_messages for c in defaults)<5:
        raise RuntimeError("Discord requiere al menos cinco canales predeterminados visibles y escribibles.")
    await guild.edit(rules_channel=channel(guild,"normas"),public_updates_channel=channel(guild,"administración"),preferred_locale=discord.Locale.spain_spanish,default_notifications=discord.NotificationLevel.only_mentions,reason="Nexora v4")
    route=Route("GET","/guilds/{guild_id}/onboarding",guild_id=guild.id)
    existing=await client.http.request(route)
    if existing.get("prompts"):
        print("Se conservan preguntas de incorporación existentes.")
    else:
        payload={"prompts":[{"id":"0","title":"¿Qué te interesa de Nexora?","type":0,"single_select":False,"required":False,"in_onboarding":True,"options":[{"id":str(i+1),"title":title,"description":desc,"channel_ids":[str(channel(guild,n).id) for n in channels],"role_ids":[]} for i,(title,desc,channels) in enumerate([("Gaming","Juegos y conversaciones",["gaming","memes"]),("Desarrollo","Novedades y sugerencias",["roadmap","sugerencias"]),("Comunidad","Conoce a otros miembros",["general","presentaciones"])])]}],"default_channel_ids":[str(c.id) for c in defaults],"enabled":True,"mode":0}
        await client.http.request(Route("PUT","/guilds/{guild_id}/onboarding",guild_id=guild.id),json=payload)
        print("OK incorporación y preguntas sin roles privilegiados")
    rules=await guild.fetch_automod_rules()
    if not any(r.trigger.type==discord.AutoModRuleTriggerType.spam for r in rules):
        await guild.create_automod_rule(name="Nexora · Antispam",event_type=discord.AutoModRuleEventType.message_send,trigger=discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam),actions=[discord.AutoModRuleAction(),discord.AutoModRuleAction(channel_id=channel(guild,"registro-de-incidencias").id)],enabled=True,reason="Nexora v4")
    print("OK revisión antispam")
    print("MANUAL: guía del servidor, alertas de seguridad, CAPTCHA/MD, revisión de incorporación y limpieza de canales.")

async def identity(guild,client):
    errors=0
    for folder,extensions,limit in [("emojis",(".png",".gif",".jpg",".webp"),256*1024),("stickers",(".png",),512*1024),("sounds",(".mp3",".ogg"),512*1024)]:
        files=sorted(p for p in (ROOT/folder).glob("*") if p.suffix.lower() in extensions)
        if not files:
            print(f"PENDIENTE {folder}: no hay recursos locales.")
            continue
        if folder=="emojis": existing={e.name for e in await guild.fetch_emojis()}
        elif folder=="stickers": existing={s.name for s in await guild.fetch_stickers()}
        else:
            data=await client.http.request(Route("GET","/guilds/{guild_id}/soundboard-sounds",guild_id=guild.id))
            existing={s["name"] for s in data["items"]}
        for p in files:
            name=p.stem
            if name in existing:
                print(f"OMITIDO existente: {name}")
                continue
            try:
                if p.stat().st_size>limit: raise ValueError("Archivo demasiado grande")
                if folder=="emojis": await guild.create_custom_emoji(name=name,image=p.read_bytes(),reason="Nexora Identity")
                elif folder=="stickers": await guild.create_sticker(name=name,description="Nexora Identity",emoji="🤖",file=discord.File(p),reason="Nexora Identity")
                else:
                    mime="audio/mpeg" if p.suffix.lower()==".mp3" else "audio/ogg"
                    await client.http.request(Route("POST","/guilds/{guild_id}/soundboard-sounds",guild_id=guild.id),json={"name":name,"sound":"data:"+mime+";base64,"+base64.b64encode(p.read_bytes()).decode(),"volume":1.0})
                existing.add(name)
                print(f"OK {folder}/{name}")
            except (discord.HTTPException,ValueError) as exc:
                errors+=1
                print(f"REVISAR {folder}/{name}: {exc}")
    print(f"Importación terminada: {errors} errores. No se reemplazan recursos existentes.")
