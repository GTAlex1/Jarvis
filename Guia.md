# Guía de JARVIS

## Ejecutable de Windows

GitHub Actions compila `jarvis_gui.py` con PyInstaller y comprueba en Windows el arranque, la bandeja, la instancia única, los motores de voz dentro del ejecutable y la sustitución y recuperación del archivo anterior. El flujo también comprueba el límite de descarga del actualizador y publica la wiki y la versión después de las pruebas. El resultado se adjunta como `JARVIS-Windows-x64` a la ejecución. Puedes abrir la [última compilación](https://github.com/GTAlex1/Jarvis/actions/workflows/windows.yml) desde el repositorio.

## Ciclo de vida del asistente

- `assistant.py` ofrece la ejecución de comandos en serie. Un futuro origen de entrada puede enviar texto mediante `Assistant.submit()` y recibir el resultado sin depender del panel.
- `resident.py` coordina la sesión de escritorio, las preferencias y el actualizador. El panel de `jarvis_gui.py` se crea al abrirlo por primera vez.
- `windows_tray.py` registra el icono con Win32. Un mutex por sesión de Windows limita JARVIS a una instancia. Una segunda apertura manual solo pide mostrar el panel existente. La bandeja recupera el icono al reiniciarse Explorer.
- `preferences.py` guarda la preferencia del micrófono y administra el inicio de sesión en el registro del usuario. `--background` inicia JARVIS en la bandeja. Para probarlo desde el código usa `python jarvis_gui.py --background`.

Los comandos y la consulta de actualizaciones se completan en segundo plano. El panel procesa los eventos de la bandeja y los resultados mediante una cola y suspende la animación al ocultarse. El dictado manual de consola conserva su confirmación antes de ejecutar una orden.

## Ventanas y pantallas

- Ejecuta `pantallas` para ver los identificadores disponibles. Las coordenadas pueden ser negativas cuando un monitor está a la izquierda o encima del principal.
- Prueba `VSCode izquierda`, `Chrome derecha monitor 2` o `Visual Studio Code pantalla completa`. Al maximizar, JARVIS usa el monitor indicado o el principal si lo omites.
- Ejecuta `ventanas` para ver los programas y sus títulos. Si hay dos ventanas de VS Code, usa una parte del título que identifique la ventana que quieres mover.
- Si la aplicación limita su tamaño mínimo, el asistente muestra las dimensiones solicitadas y las que consiguió aplicar.

## Motores de voz

| Componente | Uso | Empaquetado |
| --- | --- | --- |
| PocketSphinx 5.0.4 | Detecta «Jarvis» con un pequeño diccionario de pronunciaciones y sensibilidades configurables. | Wheel x64 de Python 3.12 y modelo acústico incluido. |
| Vosk 0.3.45 y modelo español `vosk-model-small-es-0.42` | Transcribe en español después de activar la escucha. El modelo se descarga al preparar la compilación, se comprueba con SHA-256 y se libera al pasar 30 segundos de inactividad. | DLL x64 y modelo local. El modelo está distribuido bajo Apache 2.0. |
| NumPy 2.2.6 y audioop | Filtrado antialias y conversión de PCM a 16 kHz en CPU. | La compilación incluye NumPy, sus avisos de licencia y el audioop de Python 3.12. |
| sounddevice 0.5.6 y PortAudio | Enumeran rutas y capturan en un formato aceptado por WASAPI, MME o DirectSound. | DLL x64. `RawInputStream` usa buffers de bytes. |
| System.Speech | Enumera y usa las voces clásicas instaladas de Windows mediante su PowerShell integrado. | Viene de Windows. JARVIS le pasa texto y volumen por la entrada estándar. |

Se eligió un detector pequeño para la espera y un transcriptor separado para la orden. El reconocimiento nativo de System.Speech se conserva en la consola y depende del motor español instalado. El ejecutable integra un transcriptor español para la escucha permanente. Los motores de voz pueden funcionar sin servicios externos.

El trabajador de voz conserva solo un tramo breve de audio y una cola acotada en memoria. Al detectar la palabra de activación, entrega al transcriptor el audio que sigue al final de la palabra y abre una ventana de seis segundos. Envía el texto al mismo ejecutor de comandos del panel. Descarta la captura durante la respuesta y durante el margen posterior de 450 ms, y reinicia el detector antes de volver a esperar. Si un flujo se interrumpe, intenta otra ruta del dispositivo. Cuando se agotan las opciones, actualiza la lista y vuelve a intentarlo cada tres segundos.

Fuentes de los componentes. [PocketSphinx](https://pocketsphinx.readthedocs.io/en/stable/config_params.html) · [Modelos de Vosk](https://alphacephei.com/vosk/models) · [sounddevice](https://python-sounddevice.readthedocs.io/) · [System.Speech](https://learn.microsoft.com/dotnet/api/system.speech.synthesis.speechsynthesizer)

## Conversación local

`dialogue.py` conserva un contexto temporal con la última respuesta, páginas de información y opciones de aclaración. Recibe una orden y el resultado del ejecutor para producir una respuesta hablada. Una pantalla nunca es necesaria para continuar. El historial conserva el resultado escrito de escritorio por separado. Si añades una función, puedes devolver una aclaración con opciones explícitas o convertir su resultado en páginas habladas.

La espera inicial sigue siendo de seis segundos. Después de una respuesta se abre una escucha de seguimiento durante el tiempo configurado. Al acabar esa escucha vuelve a requerirse la palabra de activación. El último tema o respuesta dura hasta agotar el contexto. Las aclaraciones con una acción pendiente se descartan cuando expira su espera. El seguimiento exige más confianza en la transcripción que una orden que empieza con la palabra de activación.

Durante la síntesis el reconocedor de órdenes permanece excluido. Un reconocedor con una gramática independiente escucha únicamente «Jarvis, para», «Jarvis, cancela» o «Jarvis, detente» con confianza alta, y su única acción es cancelar la salida. Los segmentos que pronuncian «Jarvis» desactivan temporalmente esa detección. **Detener respuesta de voz** en la bandeja puede cancelar cualquier segmento. La captura descarta el audio anterior y espera un margen de 450 milisegundos antes de volver a reconocer órdenes. La respuesta acústica de cada sala se comprueba físicamente.

## Diagnóstico de captura y reconocimiento

La 0.6.1 agrupaba las interfaces de cada dispositivo y escogía WASAPI si abría el flujo a su frecuencia anunciada. Un nivel RMS positivo bastaba para aceptar la ruta. Para el caso comunicado, el formato resultante fue 192 kHz mono int16. El conversor anterior reducía frecuencias sin un filtro antialias. En una reproducción sintética de 192 kHz, un tono de 31 kHz aparecía a 1 kHz tras la conversión anterior. Esto demuestra un defecto de la ruta y una limitación del diagnóstico de señal. La prueba física debe confirmar qué entregaba el controlador en ese equipo.

La 0.6.2 mantiene la agrupación y restaura la selección independiente de la interfaz. El modo automático empieza por MME y DirectSound y conserva WASAPI como alternativa. Prueba formatos propios de voz antes de un formato anunciado como 192 kHz, y aplica un filtro de paso bajo con estado antes de reducir la frecuencia. Seleccionar una interfaz fija permite reproducir una ruta del controlador de forma controlada. La selección antigua de una interfaz se conserva cuando su alias sigue disponible. Los identificadores agrupados de 0.6.1 pasan al modo automático si carecían de interfaz explícita.

La prueba **Probar micrófono** mide señal PCM, usa detección local de actividad de voz y presenta hipótesis y palabras confirmadas del reconocedor español. No ejecuta órdenes. En modo automático prueba otra ruta si la actual falla al capturar o no reconoce voz y palabras durante la prueba. Durante la escucha habitual, dos activaciones seguidas sin orden reconocida pueden cambiar de interfaz. La palabra de activación sigue siendo necesaria para ejecutar comandos. El registro técnico está en `%LOCALAPPDATA%\JARVIS\voz.log` y rota a 256 KiB.

### WASAPI y ASIO en 0.6.3

La prueba de 0.6.2 descartaba todo el dispositivo WASAPI si el primer formato con señal no producía palabras. Se reprodujo con un controlador simulado que aceptaba varios formatos. Ahora se consulta primero el formato compartido de WASAPI, se distinguen canales y tipo de muestra y se reintentan hasta tres formatos con señal antes de agotar esa ruta. Si Windows no proporciona el formato compartido se mantienen las pruebas de frecuencia, canales y formato. MME y DirectSound siguen disponibles en Automática. La causa concreta que impide el reconocimiento con determinados controladores Realtek queda pendiente de probar con el hardware.

La interfaz que muestra el panel depende de las rutas que el controlador expone para el micrófono seleccionado. Una interfaz detectada puede entregar audio insuficiente para el reconocimiento. Si desaparece la que estaba guardada, se avisa y se usa Automática con el mismo micrófono. Consulta la [referencia de formatos de PortAudio](https://files.portaudio.com/docs/v19-doxydocs-dev/pa__win__wasapi_8h.html).

Los requisitos de empaquetado, actualización y licencias están en [AGENTS.md](AGENTS.md). La [hoja de ruta](ROADMAP.md) reúne las funciones pendientes.

## Pruebas automatizadas

- `python -m unittest -v test_commands test_resident test_voice test_audio_input test_dialogue` comprueba comandos, bandeja, preferencias, reintento ante desconexión simulada, tratamiento de baja confianza y exclusión del audio durante la respuesta. Con los modelos y dependencias instalados, también procesa audio sintético. Las pruebas de captura simulan formatos rechazados, 48 kHz estéreo, flujo silencioso, alternativas entre APIs y un cambio del predeterminado. También comprueba filtrado y decimación de 192 kHz, continuidad a 44,1 kHz, migración de interfaces, transcripción en directo y cambio de ruta ante fallos de reconocimiento. En Windows se comprueban las consultas nativas de endpoint y asignador. Las pruebas de conversación cubren la lectura por partes, el seguimiento, la expiración, la repetición, la cancelación y las aclaraciones sin panel. Los formatos alternativos de WASAPI y la pérdida de una interfaz guardada se prueban con controladores simulados.
- El diagnóstico del ejecutable abre las DLL y usa los modelos empaquetados para reconocer «Jarvis, abre Spotify» de corrido y con pausa. También comprueba una orden sin activación, el tiempo de espera, la enumeración de dispositivos y la síntesis en memoria, y reconoce una orden sintética capturada a 192 kHz con un tono fuera de banda añadido. El diagnóstico también verifica una orden sintética de seguimiento sin palabra de activación y que la gramática de síntesis admite «Jarvis, para» e ignora una orden normal. El diagnóstico usa audio sintético y no acciona Spotify.
- `python -m unittest -v test_update_windows` comprueba el reinicio del ejecutable y la recuperación ante un arranque fallido. Requiere `dist/JARVIS.exe`. En CI también sustituye el ejecutable publicado de 0.4.1 usando el mecanismo de esa versión y comprueba el arranque de 0.6.3.

Desde un checkout del proyecto, puedes ejecutar el mismo diagnóstico del binario:

```powershell
Start-Process .\dist\JARVIS.exe -ArgumentList '--diagnostico-voz', 'tests/voice', 'diagnostico-voz.json' -Wait
Get-Content diagnostico-voz.json -Encoding UTF8
```

## Pruebas con tu micrófono

| Prueba manual | Resultado esperado |
| --- | --- |
| Selecciona tu micrófono, activa la escucha permanente y cierra el panel con la X. Di «Jarvis, abre Spotify» de corrido. | Spotify se abre y JARVIS responde con el panel oculto. |
| Di «Jarvis», espera un segundo y di «abre la calculadora». Repite dejando pasar más de seis segundos. | La primera orden se ejecuta. La segunda necesita volver a decir «Jarvis». |
| Con el panel oculto, pide «Jarvis, ayuda», di «ventanas» y luego «sí», «repite» y «no». | JARVIS da ayuda hablada, conserva el tema y termina la conversación. |
| Con dos ventanas del mismo programa abiertas, pide «Jarvis, cierra Firefox» y di «la segunda» cuando enumere las opciones. | Elige la ventana anunciada y envía la solicitud normal de cierre. |
| Con tus altavoces activos, interrumpe un tramo de una respuesta larga diciendo «Jarvis, para». Repite con el control de la bandeja. | La respuesta se corta y el altavoz no provoca órdenes de escritorio por realimentación. |
| Con el micrófono que usas normalmente, selecciona MME y luego DirectSound. En cada prueba di «abre Spotify». Repite con WASAPI y Automática. | Distingue señal, actividad de voz y palabras reconocidas. Compara la transcripción y anota interfaz y frecuencia. |
| Con la ruta que transcriba bien, guarda los ajustes y prueba «Jarvis, abre Spotify» con el panel oculto y tus demás aplicaciones de audio abiertas. | La orden se ejecuta desde la captura física habitual. |
| Con **Predeterminado de Windows** activo, cambia la entrada en Configuración de Windows con JARVIS escuchando. | El medidor y las siguientes órdenes pasan al nuevo dispositivo. |
| Desenchufa el micrófono USB, vuelve a conectarlo y repite una orden. Si tienes varios dispositivos, cambia de entrada en el panel. | Se indica la pérdida de entrada y se recupera al volver a detectar el dispositivo elegido. |
| Cambia voz, volumen y sensibilidad. Sal completamente, vuelve a abrir y comprueba los ajustes. | Se conservan las preferencias y se aplica la voz y el volumen seleccionados. |
| Desmarca **Micrófono** y prueba a activar JARVIS. Después vuelve a marcarlo y desactiva **Escucha permanente**. | Ambas opciones detienen la escucha. Puedes seguir escribiendo órdenes. |

Estas comprobaciones dependen de tu voz, el micrófono, el volumen, el ruido de la habitación y los controladores del equipo.

## Añadir un comando

1. Añade la frase al analizador de `commands.py` y conecta la acción en `execute()` de `jarvis.py`.
2. Separa la interpretación del texto de la acción de Windows, como hacen `parse_move()` y `Desktop.move()`.
3. Incluye un ejemplo en `HELP` y documenta el comando en el README.
4. Comprueba la frase válida, una variante y una entrada inválida. Para cambios en las ventanas, comprueba también una ventana maximizada y un monitor secundario.

Con Explorer activo, la prueba de bandeja verifica que el panel vuelva a abrirse desde la instancia existente.

## Comandos desde la versión 0.4.0

La tabla completa de acciones está en [README.md](README.md#órdenes-de-windows). El analizador está en `commands.py`. Devuelve una acción y sus argumentos, que `execute()` aplica mediante `Desktop`.

`rectangle()` calcula las mitades, esquinas y posiciones usando coordenadas de Windows. Se prueban monitores con coordenadas negativas y dimensiones impares.

Ejecuta `python -m unittest -v test_commands` para comprobar las frases de ejemplo, la selección de ventanas y la geometría. En Windows, también se crea una ventana de prueba para comprobar posiciones, minimizar, maximizar, restaurar y recibir una solicitud de cierre que la ventana puede rechazar. Las pruebas no bloquean la sesión ni cambian el volumen.

El flujo de publicación ejecuta esas pruebas antes de generar el ejecutable y publicar la versión.
