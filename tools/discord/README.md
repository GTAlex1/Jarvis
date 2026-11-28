# Nexora Server Builder (experimental)

Herramienta independiente de JARVIS. No se incluye en el ejecutable.

1. Crea un servidor vacío llamado Nexora desde Discord.
2. En https://discord.com/developers/applications crea una aplicación y su bot.
3. En Installation configura Guild Install con scope bot y permiso Administrador temporal. Autoriza únicamente en el servidor Nexora vacío. No actives intents privilegiados.
4. Activa modo desarrollador en Discord y copia el ID del servidor.
5. Descarga esta carpeta y abre PowerShell en ella. Con Python 3.10+:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_server.py
.\.venv\Scripts\python.exe setup_server.py --guild ID_DEL_SERVIDOR --apply
```

Sustituye ID_DEL_SERVIDOR por el ID numérico. El token del bot se solicita oculto localmente. Nunca lo publiques ni lo envíes por chat. No uses tokens de usuario.

El modo sin --apply no realiza conexiones. El modo apply comprueba nombre e ID y pide confirmación. No elimina canales ni roles, pero modifica permisos de las categorías gestionadas; úsalo solo en un servidor nuevo dedicado. Los canales iniciales de Discord no se eliminan. Repetir con el mismo bot evita duplicar mensajes idénticos y recursos con nombres únicos.

Tras terminar, verifica los permisos con la vista como rol y retira el permiso Administrador al bot o expúlsalo. El rol Nexora creado es un marcador sin permisos globales, distinto del rol gestionado por Discord del bot.

Pendiente: prueba real de API, AutoMod, nivel de verificación, jerarquía visual, permisos de moderación, foros, tickets privados y auditoría completa de permisos. No invites usuarios hasta revisar estos puntos. No se requiere alojamiento permanente.

No se ha publicado una release de JARVIS ni se ha creado el servidor mediante este código todavía.

## Interfaz v2
Abre Abrir-Nexora.cmd. Personalizar renombra categorías conservando IDs, ordena roles, configura verificación media, añade embeds y AutoMod de menciones. Crea foros adicionales si Comunidad está habilitada. Auditar revisa accesos básicos sin modificar el servidor. No borra canales iniciales ni mensajes. No concede permisos de moderación ni retira Administrador automáticamente. Revisa manualmente los resultados. La v2 aún no se ha probado contra Discord.

## v3.0
Tras Personalizar y habilitar Comunidad, pulsa Configurar permisos v3. Developer gestiona mensajes e hilos en Desarrollo e Insider; Moderator puede expulsar, banear, moderar y gestionar mensajes e hilos, sin Administrador ni gestión de roles. Nexora AI sustituye el rol visual duplicado. Auditar sigue siendo una comprobación básica. Retirar Administrador es una operación independiente y debe hacerse al final; si Discord impide editar el rol gestionado, retira el permiso manualmente. No se eliminan canales. No se ha probado v3 en Discord.
