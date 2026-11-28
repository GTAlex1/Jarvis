# Catálogo de aplicaciones y videojuegos de JARVIS

Estado de la versión 0.6.5-rc.2: candidata de validación interna. La cobertura depende de los metadatos que cada cliente exponga en el equipo.

## Arquitectura

1. `windows_catalog.py` consulta Windows una vez por actualización. Lee AppsFolder, menú Inicio, paquetes del usuario, accesos del escritorio y de Inicio, App Paths y metadatos de desinstalación de ambas vistas del registro. Busca portables en `%USERPROFILE%\PortableApps`, `%USERPROFILE%\Games` y carpetas elegidas por el usuario. La búsqueda local tiene límite de profundidad y cantidad de archivos, no sigue enlaces ni uniones de directorios y no recorre unidades completas.
2. `game_providers.py` incorpora fuentes de los clientes. Los proveedores pueden suministrar una ruta de lanzamiento, identidades para comprobar el proceso o una ficha que indique que el arranque no está disponible. Un título puede tener varias instalaciones o proveedores.
3. `app_catalog.py` conserva en memoria la última generación completa. Un trabajador escribe `%LOCALAPPDATA%\JARVIS\applications-v1.json` de forma atómica. El archivo contiene nombres y rutas locales, no credenciales. La caché caduca tras 30 minutos y se actualiza al iniciar o consultar si ha caducado. Puedes invalidarla con `actualiza aplicaciones`. El primer comando tras una instalación limpia puede esperar la primera carga en el hilo de comandos. El panel continúa operativo.
4. `jarvis.py` resuelve un destino antes de autorizar una orden de voz. Un nombre, alias o ejecutable exacto tiene prioridad. Las abreviaturas inferidas y las correcciones ortográficas o fonéticas piden confirmación, incluso si la lista contiene un único resultado. El nombre y la fuente distinguen instalaciones simultáneas. El identificador de una selección se valida otra vez antes de usarla.
5. `windows_instances.py` y `app_launch.py` separan proceso, paquete y ventana. Comprueban rutas completas de ejecutables, AUMID del proceso o una ventana dentro de la raíz que declara el cliente. Para títulos con un ejecutable de juego conocido se excluyen los lanzadores, actualizadores y auxiliares. El cierre normal usa `WM_CLOSE`, por lo que la aplicación puede pedir guardar cambios. Las órdenes globales que usan atajos siguen informando del envío de la tecla.

## Fuentes por proveedor

| Proveedor | Fuente que consulta | Qué se puede solicitar |
| --- | --- | --- |
| Steam | Registro, rutas habituales, `libraryfolders.vdf` y `appmanifest_*.acf` | Solicitud por ID a Steam. Comprueba una ventana del juego bajo la biblioteca detectada. |
| Epic Games | Manifiestos `.item` y accesos directos del cliente | Activación del producto con el protocolo de Epic; se comprueba el ejecutable o la ventana del juego. |
| Riot Client | Accesos del cliente, registro y asociaciones en `RiotClientInstalls.json` | Abre el acceso específico. Riot puede pedir pulsar **Jugar** en la ficha; el cliente por sí solo no confirma el arranque. |
| HoYoPlay | Accesos directos compatibles y metadatos publicados por el instalador | Usa el acceso del juego cuando existe. Si solo hay metadatos, solicita crear el acceso desde el cliente. |
| Xbox / PC Game Pass | Paquetes registrados, AUMID y `MicrosoftGame.config` accesible | Activación por Windows, sujeta a licencia, edición e inicio de sesión. Los paquetes con metadatos restringidos pueden aparecer como una aplicación genérica de Windows. |
| EA App | Accesos directos compatibles y metadatos de desinstalación | Lanza solo cuando dispone de una ruta específica del juego; si no, muestra que falta la ruta. |
| Ubisoft Connect | Accesos directos, claves de instalación y productos que incluyen el nombre | Solicitud `uplay://launch/` con el ID instalado o acceso directo. |
| Battle.net | Accesos directos con destino a un producto y metadatos de desinstalación | Solicita la apertura por el cliente cuando encuentra un acceso válido. No garantiza que el cliente admita el arranque directo. |
| GOG Galaxy | Accesos directos y registro `GOG.com\Games` | Usa el acceso al producto o el ejecutable de un instalador independiente cuando está registrado bajo la carpeta del juego. |
| PWA de navegador | Entradas de Inicio y accesos de Chrome o Edge con AppUserModelID propio | Windows abre su acceso registrado. La ventana se comprueba por su identidad, sin contar una ventana normal del navegador. |\n| Independientes | AppsFolder, accesos locales, registro y carpetas portables | Lanza el ejecutable o acceso validado localmente. |

El índice nunca ejecuta `UninstallString`, ni toma la frase del usuario como ruta, argumentos o script. No se fuerzan cierres, no se automatizan clics de inicio de sesión ni se alteran los sistemas anticheat. Los juegos tienen 45 segundos de comprobación asíncrona. Si aparece un proceso del juego sin ventana, el plazo puede extenderse hasta 30 segundos desde ese momento. Puedes seguir dando órdenes y consultar «estado del arranque». Un proceso observado tampoco confirma que la partida o la pantalla principal esté lista. En el comando «pantalla completa» se comprueba maximización de Windows; el modo exclusivo dependerá del propio juego. El destino «navegador» presenta opciones si hay varios compatibles.

Referencias: [identidades de aplicación en Windows](https://learn.microsoft.com/es-es/windows/configuration/store/find-aumid), [registro de aplicaciones Win32](https://learn.microsoft.com/en-us/windows/win32/shell/app-registration), [activación por protocolo de Epic](https://dev.epicgames.com/docs/epic-games-store/protocol-activation) y [flujo de inicio de Riot](https://support.riotgames.com/en-us/riot/client/riot-client-faq).

Cada lectura se aísla por fuente. Una fuente fallida puede recuperar fichas válidas de la generación anterior. Un acceso a Minecraft Java puede abrir la selección del launcher; en esa ruta, JARVIS no verifica instancias Java genéricas. La edición Bedrock usa la identidad registrada en Windows cuando está disponible. Se conservan las rutas específicas de los clientes y sus comprobaciones de autenticación y anticheat.
