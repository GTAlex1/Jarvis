import discord
from setup_server import unique, ROLES
from maintenance import ICONS

async def permissions(guild, client):
    me=guild.me
    if not me or not me.guild_permissions.administrator:
        raise RuntimeError("Se requiere Administrador temporal.")
    roles={n:unique([r for r in guild.roles if not r.managed],n) for n in ROLES if n!="Nexora"}
    visual=unique([r for r in guild.roles if not r.managed],"Nexora AI") or unique([r for r in guild.roles if not r.managed],"Nexora")
    if any(r is None or r>=me.top_role for r in [*roles.values(),visual]):
        raise RuntimeError("Faltan roles o la jerarquía impide editarlos.")
    dev=roles["Developer"]
    mod=roles["Moderator"]
    await dev.edit(permissions=discord.Permissions.none(),reason="Nexora v3")
    await mod.edit(permissions=discord.Permissions(kick_members=True,ban_members=True,moderate_members=True,manage_messages=True,manage_threads=True,view_audit_log=True),reason="Nexora v3")
    await visual.edit(name="Nexora AI",permissions=discord.Permissions.none(),reason="Nexora v3")
    await me.add_roles(visual,reason="Nexora identidad")
    for name,icon in [("DESARROLLO",ICONS[2]),("NEXORA INSIDER",ICONS[3])]:
        cat=unique(guild.categories,f"{icon}・{name}") or unique(guild.categories,name)
        if not cat: raise RuntimeError(f"Falta {name}")
        for channel in [cat,*cat.channels]:
            overwrite=channel.overwrites_for(dev)
            overwrite.manage_messages=True
            overwrite.manage_threads=True
            await channel.set_permissions(dev,overwrite=overwrite,reason="Nexora desarrollo")
        print(f"OK permisos de desarrollo: {name}")
    print("OK permisos de moderación y rol Nexora AI")
    print("Revisa jerarquía y permisos efectivos antes de finalizar.")

async def finalize(guild,client):
    me=guild.me
    if not me: raise RuntimeError("Bot no disponible")
    if guild.default_role.permissions.administrator:
        raise RuntimeError("@everyone tiene Administrador; corrígelo manualmente.")
    admin=[r for r in me.roles if r.permissions.administrator]
    for role in admin:
        if role.tags is None or role.tags.bot_id!=client.user.id:
            raise RuntimeError("Administrador procede de un rol compartido; retíralo manualmente.")
    for role in admin:
        p=role.permissions
        p.administrator=False
        await role.edit(permissions=p,reason="Nexora fin de configuración")
        print(f"OK retirada de Administrador: {role.name}")
    print("Comprueba los permisos restantes del bot en Discord. No se han eliminado canales.")
