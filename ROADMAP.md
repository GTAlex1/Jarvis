# Hoja de ruta de JARVIS y Nexora

Nexora es el nombre provisional desde 0.7.0. Se revisará su disponibilidad legal y comercial antes del cambio de marca. Las versiones siguientes son objetivos revisables. La seguridad se valida desde las primeras revisiones.

## 0.6.x · Fundamentos

| Versión | Alcance |
| --- | --- |
| 0.6.4 | Reconocimiento avanzado y seguridad de voz. |
| 0.6.4.1 | Diagnóstico biométrico, corrección de BUG-064-001 y perfiles de seguridad. El propietario validó persistencia y órdenes tras una pausa. |
| 0.6.4.2 | Voice & Recognition Overhaul. Validación interna de activación continua, reconocimiento, adaptación voluntaria, seguridad y actualizador. |
| 0.6.5 | Universal Application Intelligence. Candidata con catálogo local y comprobación del arranque; queda pendiente validar el comportamiento real de los clientes en Windows. |
| 0.6.5.1 | Infraestructura de betatesting, diagnósticos voluntarios, feedback, canales de actualización y recuperación. |
| 0.6.5.2 | Fase A: servidor oficial de Discord. Fase B: bot comunitario e integraciones. |
| 0.6.5.3 | Nexora Hub con sugerencias, votaciones, feedback, panel de administración y sincronización con Discord. |
| 0.6.6 | Gaming Intelligence. Perfiles de juego, recursos, optimización de audio y llamadas, notificaciones, comandos en juego y apertura de aplicaciones sin robar el foco cuando el sistema lo permita. |

### Validación física de JARVIS 0.6.4.2

El propietario registró **8 pruebas correctas, 1 parcialmente correcta, 3 fallidas y 1 pendiente**. En su equipo funcionaron la actualización automática desde 0.6.4.1, la conservación de micrófono, perfil y ajustes de seguridad, la activación en una frase y con pausa, la prueba del perfil biométrico, el bloqueo de órdenes ajenas en los escenarios probados y la coexistencia de audio con Discord y WhatsApp.

Sigue pendiente comprobar las activaciones accidentales durante conversaciones y ampliar las pruebas de seguridad con más escenarios y hablantes. También queda por mejorar el reconocimiento de órdenes naturales, incluidas variantes coloquiales como «cerrá Spotify» y «quítame Spotify». La revisión sigue destinada a validación interna.

### Resultados de la primera candidata de 0.6.5

En rc.1, la referencia a game_roots interrumpió el catálogo en los equipos que tenían ejecutables indexados. El propietario reprodujo el fallo con Poke Gacha Online, Rocket League y Genshin Impact. También encontró nombres técnicos en las confirmaciones y errores al transcribir nombres extranjeros. rc.2 corrige el ámbito de game_roots, incorpora identidades de ventana, sugiere nombres usando el catálogo y ofrece un modelo inglés local. La comprobación física de Epic y HoYoPlay sigue pendiente.

La rc.2 adelanta solo el reconocimiento necesario para resolver aplicaciones y juegos. La comprensión conversacional, los acentos y expresiones regionales siguen en 0.9.0.1.

### Detección y ejecución de videojuegos

| Resultado físico de 0.6.4.1 | Qué se comprobará en 0.6.5 |
| --- | --- |
| Valorant abre Riot Client. | Arranca Valorant y se verifica el proceso o ventana correspondiente. |
| Honkai: Star Rail abre HoYoPlay. | Arranca el juego solicitado y se distingue su resultado del launcher. |
| Rocket League presenta problemas de detección y apertura mediante Epic. | Detecta la instalación compatible, usa el mecanismo de Epic y comprueba el arranque. |
| Steam funcionó en el equipo del propietario. | Conserva el caso como regresión física. |

La cobertura prevista incluye Steam, Epic Games, Riot Client, HoYoPlay, Battle.net, Ubisoft Connect, EA App, Xbox, Microsoft Store, GOG Galaxy y aplicaciones o juegos independientes y portables. El ejecutor distinguirá la aplicación solicitada del launcher, respetará las vías admitidas y verificará el resultado observable. [Incidencia de seguimiento](https://github.com/GTAlex1/Jarvis/issues/1)

### Nexora Insider y Discord

Los primeros betatesters externos podrán incorporarse a partir de 0.6.5.1 una vez comprobados el bloqueo de órdenes ajenas, la estabilidad, la coexistencia de audio y la recuperación del actualizador. Los diagnósticos serán voluntarios y excluirán audio y firmas. La beta cerrada oficial sigue prevista para 0.7.0.

- **Fase A · Servidor privado.** Se adelantó el intento de configuración en Discord Web. La creación y la verificación siguen pendientes: la aplicación web se quedó en la pantalla de conexión. La fase incluye información, anuncios, descargas, changelog, roadmap, comunidad, gaming, sugerencias, votaciones, errores, soporte, canales de voz y espacios privados para Insider, Zero Division y administración. La apertura a usuarios externos se decidirá por separado.
- **Fase B · Bot e integraciones.** Quedan pendientes el bot comunitario, los avisos de GitHub, la publicación automática de versiones y changelogs y la gestión de tickets y del programa Insider. La sincronización con Nexora Hub sigue prevista para 0.6.5.3. La 0.6.5.2 sigue abierta.

Roles previstos: Founder, Developer, Moderator, Zero Division, Nexora Insider, Early Adopter, Member y Nexora. Zero Division será un reconocimiento exclusivo para los betatesters originales.

## 0.7.x · Identidad y experiencia de usuario

| Versión | Alcance |
| --- | --- |
| 0.7.0 | Cambio de marca a Nexora, rediseño inspirado en Apple Liquid Glass y beta cerrada oficial. |
| 0.7.1 | HUD flotante, animaciones, indicadores e infraestructura para subtítulos y superposiciones. |
| 0.7.2 | Accesibilidad, dictado, control avanzado por voz y reconocimiento avanzado de variedades lingüísticas. Se evaluará la palabra de activación personalizable. |
| 0.7.3 | Instalador oficial Nexora-Setup.exe y distribución Nexora-Portable.exe. |

El instalador contempla dependencias y modelos automáticos, migración desde JARVIS, accesos directos, inicio opcional, actualizaciones, reparación, desinstalación y elección sobre conservar o borrar datos. Se prioriza instalar sin administración cuando sea viable y se evaluará la firma digital.

## 0.8.x · Automatización e integraciones

| Versión | Alcance |
| --- | --- |
| 0.8.0 | Integraciones modulares con Discord, Spotify, OBS, Steam, VS Code y otras aplicaciones. |
| 0.8.1 | Rutinas, automatizaciones y tareas programadas. |
| 0.8.2 | Historial y deshacer acciones reversibles. |
| 0.8.5 | Voces neuronales locales naturales, perfiles masculinos y femeninos descargables y personalizables con licencias adecuadas. |

## 0.9.x · Inteligencia artificial local

| Versión | Alcance |
| --- | --- |
| 0.9.0 | Nexora Intelligence, motor local adaptativo. |
| 0.9.0.1 | Nexora Voice Intelligence. Comprensión contextual, reconocimiento multilingüe avanzado, aislamiento de voz, acentos, expresiones regionales, conjugaciones, lenguaje coloquial y adaptación lingüística. Incluirá evaluación con variedades del español de España y Latinoamérica, entre ellas andaluza, mexicana, ecuatoriana, argentina, colombiana y caribeña. |
| 0.9.0.2 | Nexora Translate. Traducción escrita y hablada bajo demanda y traducción simultánea de audio seleccionado. |
| 0.9.1 | Memoria editable y aprendizaje personalizado. |
| 0.9.2 | Nexora Vision y comprensión visual de la pantalla, con futura integración de traducción visual. |
| 0.9.3 | Nexora Control, interacción con aplicaciones y automatización visual y web. |
| 0.9.3.1 | Resolución autónoma de tareas y puzles. |
| 0.9.3.2 | Planificación, verificación y autocorrección. |
| 0.9.3.3 | Nexora Learn, aprendizaje mediante demostraciones. |
| 0.9.3.4 | Rutinas adaptativas. |
| 0.9.4 | Fundamentos de Nexora Connect y control remoto. |
| 0.9.4.1 | Vinculación segura de dispositivos. |
| 0.9.4.2 | Encendido remoto compatible. |
| 0.9.4.3 | Visualización remota autorizada. |
| 0.9.5 | Catálogo de extensiones e integraciones mediante Nexora Hub. |
| 0.9.6 | Seguridad avanzada y permisos granulares. |
| 0.9.7 | Optimización, rendimiento y compatibilidad. |

### Nexora Translate

- **Bajo demanda.** Detectar el idioma, traducir texto y voz a un destino como chino mandarín o japonés, explicar el contexto y ofrecer pronunciación y romanización cuando correspondan.
- **Audio simultáneo.** Elegir una aplicación, capturar solo su audio si el sistema lo permite, detectar idiomas y omitir las intervenciones ya en el idioma de destino. Mostrar subtítulos en el HUD y reproducir voz traducida cuando se pida. Admitir órdenes para iniciar, pausar y detener.
- **Traducción visual con Vision.** Aplicar OCR a menús, interfaces o diálogos, superponer el texto traducido y explicar referencias contextuales.
- **2.0.** Prever la traducción entre dispositivos y un modo intérprete bidireccional con controles claros.
- **3.0.** Investigar la interpretación de conversaciones grupales. Informar a participantes, recabar consentimiento cuando corresponda y aplicar sus preferencias de privacidad.

0.6.5 mantiene el reconocimiento contextual de aplicaciones. 0.6.6 aborda audio y juegos, 0.7.1 aporta el HUD y 0.9.0.1 prepara el reconocimiento multilingüe avanzado. El motor de traducción corresponde a una fase posterior.

### Nexora Learn

El usuario podrá mostrar una tarea, revisar los pasos aprendidos y solicitar su repetición o programación. Una rutina conceptual «Misiones diarias» en Honkai: Star Rail deberá contemplar observación, planificación, adaptación, verificación, permisos, cancelación y errores. Su ejecución dependerá de lo que permitan las condiciones de uso y los sistemas del juego. Queda excluida la evasión de antitrampas.

## Nexora 1.0 · Asistente personal

Primera versión estable para Windows tras auditar seguridad, rendimiento y estabilidad. Objetivo de comprender instrucciones, controlar el dispositivo, interpretar su pantalla, aprender rutinas y automatizar tareas autorizadas.

## Nexora 2.0 · Ecosistema conectado

| Versión | Alcance |
| --- | --- |
| 1.1.0 | Nexora Connect. Sincronización, vinculación de cuentas y dispositivos, y control remoto seguro. |
| 1.2.0 | Adaptador para Linux. |
| 1.3.0 | Adaptador para macOS. |
| 1.4.0 | Android y Nexora Mobile Companion. |
| 1.5.0 | iOS y Nexora Mobile Companion. |
| 2.0.0 | Ecosistema con rutinas, errores y avisos remotos, e integración remota autorizada mediante Discord. |

Una solicitud desde el móvil para ejecutar «Misiones diarias» en el ordenador se vinculará a identidades verificadas, dispositivos enlazados, comunicaciones seguras, permisos independientes, caducidad, historial y cancelación. Las capacidades se comprobarán por plataforma.

## Nexora 3.0 · Inteligencia social

Nexora Social se reserva para 3.0, con posibles prototipos 2.x. El objetivo es participar en canales de voz de Discord con varios interlocutores, respetar turnos, identificar la cuenta emisora y distinguir conversación, preguntas, órdenes, bromas, sarcasmo, ironía y humor contextual. Se contempla intervención espontánea apropiada, lenguaje informal y modos Mayordomo, Colega, Sarcástico, Caótico, Profesional y Personalizado.

La memoria individual y grupal, incluidas bromas internas, requerirá consentimiento. Se informará a los participantes de cómo se procesa el audio, con grabaciones y transcripciones persistentes desactivadas por defecto. Los participantes sin Nexora instalado serán interlocutores del bot. Connect solo podrá controlar dispositivos vinculados y autorizados. La personalidad estará separada del motor de permisos y el humor no otorgará autorización. Se evaluarán viabilidad, privacidad, latencia, costes e integración con Discord.
