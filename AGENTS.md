# Desarrollo y distribución de JARVIS

JARVIS es un asistente de distribución pública. Windows es la plataforma actual. El nombre provisional Nexora y la compatibilidad futura con Linux, macOS, Android e iOS orientan la arquitectura. Desarrolla y prueba cada función para una instalación limpia y diferentes equipos.

## Requisitos de distribución

- Las funciones esenciales son gratuitas y se diseñan para ofrecer privacidad y ejecución local.
- El ejecutable publicado debe incluir las dependencias y modelos esenciales o instalarlos automáticamente. La descarga normal y la actualización no deben requerir instalar Python, DLL, modelos ni paquetes a mano.
- Las funciones esenciales deben funcionar sin claves API, cuentas externas ni GPU dedicada. Prioriza procesamiento local, uso moderado de recursos y funcionamiento sin conexión para voz y comandos.
- Empaqueta los componentes y modelos de las funciones esenciales. Si se descargan componentes nuevos durante una compilación o actualización, fija su versión y origen, verifica su integridad y gestiona los fallos sin inutilizar la instalación existente.
- Comprueba que las licencias de los componentes, modelos, voces y datos que se redistribuyen permitan la distribución pública. Incluye sus avisos y cumple las condiciones de atribución, redistribución y acceso a fuentes que correspondan.
- Mantén la actualización directa desde versiones anteriores compatibles, sin pasar por cada lanzamiento intermedio. Conserva el nombre y protocolo del recurso de actualización. Hasta que exista una migración compatible, respeta el límite de 100 MiB que comprueban los clientes antiguos.
- Conserva las preferencias del usuario. Añade valores predeterminados y migra campos o identificadores antiguos sin sustituir las demás elecciones del usuario. Conserva un mecanismo de recuperación si el ejecutable nuevo falla.
- Detecta funciones y dispositivos por sus capacidades. Evita rutas, nombres de hardware y otros supuestos exclusivos de un ordenador. Usa preferencias por usuario y rutas resueltas por Windows.

## Arquitectura y seguridad de voz

- Separa intención, diálogo, verificación y políticas de los adaptadores de escritorio, audio, cifrado y actualización. Mantén las llamadas y dependencias de Windows en adaptadores. Adopta interfaces portables al modificar módulos existentes y conserva las rutas de Windows ya verificadas.
- Trata la palabra de activación como un elemento reemplazable. Conserva el modelo, el identificador y los datos de pronunciación aislados del ejecutor, con el objetivo de poder personalizarlos en una versión futura.
- Verifica cada orden y turno cuando la biometría esté activa. La biometría es probabilística y admite riesgos de reproducción y síntesis. Ante fallos de perfiles o verificación, aplica la política sin cambiar silenciosamente el nivel de protección.
- Conserva las firmas biométricas cifradas para la cuenta local. Mantén el audio de registro en memoria y evita incluir firmas, nombres de perfiles y audio en diagnósticos.
- Usa captura compartida cuando sea posible y conserva alternativas. Los cambios globales de sonido requieren autorización del usuario.

## Verificación y publicación

- Arranca el ejecutable empaquetado en Windows y comprueba comandos, bandeja, captura y reconocimiento con los medios automatizados disponibles.
- Comprueba que el actualizador verifica la descarga, sustituye y reinicia el ejecutable y recupera la instalación anterior cuando el arranque falla. Comprueba el descubrimiento directo desde una versión anterior al publicar.
- Las pruebas automatizadas con audio sintético y dispositivos simulados deben distinguirse de las pruebas con equipos físicos, controladores, micrófonos y altavoces reales.
- Actualiza el README, la guía y la wiki. Publica solo tras superar las pruebas automatizadas del ejecutable que se va a distribuir.
- Consulta [ROADMAP.md](ROADMAP.md) para el alcance futuro. Implementa las versiones de la hoja de ruta cuando haya un encargo para ellas.

## Permisos configurables

- Trata la verificación biométrica y la política de cada categoría como ajustes independientes. La desactivación de biometría o la reducción de protección requiere consentimiento explícito en la interfaz local y no puede realizarse por voz. Los fallos de perfiles conservan la protección.
- Usa la clasificación común de `permissions.py`. Las operaciones críticas y remotas conservan la autorización local cuando corresponda. Vincula las confirmaciones a una acción concreta, a la sesión y a una caducidad. Respeta UAC y los permisos nativos. Las categorías reservadas no habilitan funciones por sí solas.
- Distingue muestra corta, ruido, silencio, saturación, falta de coincidencia y fallo de verificación. Permite repetir la orden y comprobar el perfil localmente. Una coincidencia sintética no valida a un hablante real.
- Mantén los diagnósticos exportables libres de grabaciones, transcripciones, firmas y nombres de perfiles. Registra categorías y motivos de aprobación, cancelación y rechazo.
- Desde 0.6.4.1 el actualizador reconoce hasta cuatro componentes. Los clientes anteriores requieren reemplazar manualmente el ejecutable para adoptar esta revisión. Conserva el estado local durante la sustitución.
