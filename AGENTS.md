# Desarrollo y distribución de JARVIS

JARVIS es un asistente de escritorio de distribución pública para Windows. Desarrolla y prueba cada función para una instalación limpia y para equipos distintos a los del equipo del proyecto.

## Requisitos de distribución

- El ejecutable publicado debe incluir las dependencias y modelos esenciales o instalarlos automáticamente. La descarga normal y la actualización no deben requerir instalar Python, DLL, modelos ni paquetes a mano.
- Las funciones esenciales deben funcionar sin claves API, cuentas externas ni GPU dedicada. Prioriza procesamiento local, uso moderado de recursos y funcionamiento sin conexión para voz y comandos.
- Empaqueta los componentes y modelos de las funciones esenciales. Si se descargan componentes nuevos durante una compilación o actualización, fija su versión y origen, verifica su integridad y gestiona los fallos sin inutilizar la instalación existente.
- Comprueba que las licencias de los componentes, modelos, voces y datos que se redistribuyen permitan la distribución pública. Incluye sus avisos y cumple las condiciones de atribución, redistribución y acceso a fuentes que correspondan.
- Mantén la actualización directa desde versiones anteriores compatibles, sin pasar por cada lanzamiento intermedio. Conserva el nombre y protocolo del recurso de actualización. Hasta que exista una migración compatible, respeta el límite de 100 MiB que comprueban los clientes antiguos.
- Conserva las preferencias del usuario. Añade valores predeterminados y migra campos o identificadores antiguos sin sustituir las demás elecciones del usuario. Conserva un mecanismo de recuperación si el ejecutable nuevo falla.
- Detecta funciones y dispositivos por sus capacidades. Evita rutas, nombres de hardware y otros supuestos exclusivos de un ordenador. Usa preferencias por usuario y rutas resueltas por Windows.

## Verificación y publicación

- Arranca el ejecutable empaquetado en Windows y comprueba comandos, bandeja, captura y reconocimiento con los medios automatizados disponibles.
- Comprueba que el actualizador verifica la descarga, sustituye y reinicia el ejecutable y recupera la instalación anterior cuando el arranque falla. Comprueba el descubrimiento directo desde una versión anterior al publicar.
- Las pruebas automatizadas con audio sintético y dispositivos simulados deben distinguirse de las pruebas con equipos físicos, controladores, micrófonos y altavoces reales.
- Actualiza el README, la guía y la wiki. Publica solo tras superar las pruebas automatizadas del ejecutable que se va a distribuir.
- Consulta [ROADMAP.md](ROADMAP.md) para el alcance futuro. Implementa las versiones de la hoja de ruta cuando haya un encargo para ellas.
