# JARVIS para Windows

JARVIS se queda en la bandeja del sistema y controla ventanas, aplicaciones y funciones de Windows con órdenes en español. Puedes escribirlas en el panel o activar el reconocimiento de voz local.

## Descargar y abrir

1. Descarga `JARVIS.exe` desde [GitHub Releases](https://github.com/GTAlex1/Jarvis/releases/latest).
2. Abre el ejecutable. La X oculta el panel y **Salir de JARVIS**, en la bandeja, cierra el programa por completo.
3. Si quieres que arranque al iniciar sesión, marca **Iniciar con Windows** en la bandeja.

## Activación por voz

1. En **Ajustes de voz**, elige tu micrófono y activa **Escucha permanente**. Comprueba que **Micrófono** también esté marcado en la bandeja.
2. Con el panel abierto u oculto, di «Jarvis, abre Spotify». También puedes decir «Jarvis», hacer una pausa y dar la orden dentro de los seis segundos siguientes.
3. JARVIS ejecuta el comando, responde con una voz instalada en Windows y vuelve a esperar. Puedes cambiar la voz, el volumen y la sensibilidad de activación en los ajustes.

El estado aparece en el panel y al pasar el ratón sobre el icono de la bandeja. Los modelos incluidos trabajan localmente. El audio se procesa en memoria y la entrada se descarta durante las respuestas de JARVIS. Puedes desactivar la escucha desde la bandeja y seguir usando el panel.

## Seguridad de voz en 0.6.4

Abre **Perfiles de voz** en la bandeja. Graba tres frases propias y guarda el perfil. Puedes renombrarlo, renovar sus muestras o eliminarlo. JARVIS verifica la voz al recibir órdenes y en cada seguimiento. Las firmas están cifradas para la cuenta local de Windows.

Las acciones sensibles requieren **Confirmar acción de voz** y el código que muestra el panel local. Grabaciones e imitaciones pueden superar la comprobación biométrica. Desmarca **Micrófono** en la bandeja para detener la escucha. Puedes seguir usando comandos escritos.

JARVIS usa WASAPI compartida, MME y DirectSound. Para comprobar la convivencia con Discord o WhatsApp, compara una llamada con la escucha activa y pausada. La [guía](https://github.com/GTAlex1/Jarvis/blob/main/Guia.md) separa las pruebas automatizadas de las comprobaciones físicas.

## Conversar sin abrir el panel

Di «Jarvis, ayuda» y responde «ventanas» cuando te pregunte. Puedes decir «continúa», «repite», «dame más detalles», «sí», «no» o «cancela». Las respuestas largas se pueden escuchar en partes. Si hay más de una coincidencia para una ventana o aplicación, JARVIS te pregunta cuál quieres.

Mientras habla, puedes decir «Jarvis, para» o elegir **Detener respuesta de voz** en la bandeja. **Ajustes de voz** permite cambiar el tiempo de seguimiento, la duración del contexto y el detalle de las respuestas. La voz y los comandos se procesan localmente.

## Probar un micrófono

En **Ajustes de voz** elige el micrófono y la **Interfaz de captura** por separado. **Automática** prueba rutas compatibles. El menú ofrece **MME**, **DirectSound**, **WASAPI** y **ASIO** cuando están disponibles para el micrófono elegido. Con **Predeterminado de Windows** y MME o DirectSound se pueden usar los asignadores de Windows.

Pulsa **Probar micrófono** y di «abre Spotify». La prueba separa señal, voz y palabras y muestra la transcripción en directo. En modo automático repite la frase si cambia la ruta que muestra el medidor. Puedes hacer la prueba con **Escucha permanente** desactivada.

Si necesitas distinguir problemas del controlador y del reconocimiento, abre `%LOCALAPPDATA%\JARVIS\voz.log`. Consulta las [pruebas físicas de la guía](https://github.com/GTAlex1/Jarvis/blob/main/Guia.md#pruebas-con-tu-micrófono) y la [hoja de ruta](https://github.com/GTAlex1/Jarvis/blob/main/ROADMAP.md).

## Órdenes y atajos

| Orden | Resultado |
| --- | --- |
| `abre VSCode` | Solicita a Windows abrir Visual Studio Code desde el menú Inicio. |
| `minimiza Chrome` | Minimiza las ventanas abiertas de Chrome. |
| `aplicaciones` | Lista las aplicaciones que ofrece Windows en el menú Inicio. |
| `VSCode izquierda` o `vscode izquieda` | Coloca VS Code en la mitad izquierda. |
| `Visual Studio Code pantalla completa` | Maximiza VS Code. |
| `Chrome derecha monitor 2` | Coloca Chrome en la mitad derecha del monitor 2. |
| `maximiza el Explorador en la pantalla 2` | Maximiza el Explorador en el monitor 2. |

**Pantallas** muestra los identificadores. Si omites el monitor, se usa el principal. **Ventanas** lista los programas y títulos visibles. Si hay varias coincidencias, usa un título más específico.

La [guía de desarrollo](https://github.com/GTAlex1/Jarvis/blob/main/Guia.md) explica las pruebas automáticas y qué comprobar con tu micrófono. El [README](https://github.com/GTAlex1/Jarvis#readme) incluye la lista completa de comandos y cómo probar el código fuente.

Consulta el [historial de cambios](https://github.com/GTAlex1/Jarvis/blob/main/CHANGELOG.md) y la [hoja de ruta de Nexora e Insider](https://github.com/GTAlex1/Jarvis/blob/main/ROADMAP.md).
