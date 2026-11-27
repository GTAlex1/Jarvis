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
| sounddevice 0.5.6 y PortAudio | Enumeran rutas y capturan en un formato aceptado por WASAPI, MME o DirectSound. | DLL x64. `RawInputStream` usa buffers de bytes. |
| System.Speech | Enumera y usa las voces clásicas instaladas de Windows mediante su PowerShell integrado. | Viene de Windows. JARVIS le pasa texto y volumen por la entrada estándar. |

Se eligió un detector pequeño para la espera y un transcriptor separado para la orden. El reconocimiento nativo de System.Speech se conserva en la consola y depende del motor español instalado. El ejecutable integra un transcriptor español para la escucha permanente. Los motores de voz pueden funcionar sin servicios externos.

El trabajador de voz conserva solo un tramo breve de audio y una cola acotada en memoria. Al detectar la palabra de activación, entrega al transcriptor el audio que sigue al final de la palabra y abre una ventana de seis segundos. Envía el texto al mismo ejecutor de comandos del panel. Descarta la captura durante la respuesta y durante el margen posterior de 450 ms, y reinicia el detector antes de volver a esperar. Si un flujo se interrumpe, intenta otra ruta del dispositivo. Cuando se agotan las opciones, actualiza la lista y vuelve a intentarlo cada tres segundos.

Fuentes de los componentes. [PocketSphinx](https://pocketsphinx.readthedocs.io/en/stable/config_params.html) · [Modelos de Vosk](https://alphacephei.com/vosk/models) · [sounddevice](https://python-sounddevice.readthedocs.io/) · [System.Speech](https://learn.microsoft.com/dotnet/api/system.speech.synthesis.speechsynthesizer)

## Diagnóstico de captura

En 0.6.0, elegir un dispositivo explícito hacía un único intento a 16 kHz, mono e int16. Además, los bloques de ceros digitales se trataban como una captura sana. Reproducimos ambos comportamientos con un controlador simulado. El informe de Realtek en el que funcionaba el asignador MME es compatible con un problema de formato o de la ruta de captura. El controlador y la configuración exactos del equipo requieren una prueba física.

En 0.6.1 se consulta la frecuencia del dispositivo y se sondean combinaciones de frecuencia, canales y formato con PortAudio. El reconocedor recibe PCM mono a 16 kHz tras la conversión local. Cuando un backend falla o solo entrega ceros al inicio, se prueba otra ruta del dispositivo. Para el predeterminado de Windows también se prueba el asignador MME. Si todas las rutas abiertas entregan silencio digital, queda abierta una para que puedas comprobar el nivel al hablar. La selección explícita sigue al dispositivo elegido y el modo predeterminado consulta el endpoint activo de Windows una vez por segundo.

Los alias de WASAPI, MME y DirectSound se agrupan cuando los nombres coinciden sin ambigüedad. Las selecciones antiguas se resuelven con su alias cuando siguen disponibles. El asignador seleccionado en 0.6.0 conserva preferencia por MME hasta que guardes **Predeterminado de Windows** en los ajustes. Consulta [la documentación de PortAudio](https://portaudio.com/docs/v19-doxydocs/pa__win__wasapi_8h.html) y [el enrutado de dispositivos de Windows](https://learn.microsoft.com/windows/win32/coreaudio/getting-the-default-device-endpoint-for-stream-routing).

`%LOCALAPPDATA%\JARVIS\voz.log` separa los eventos de captura y reconocimiento. Registra formatos rechazados, rutas abiertas, ausencia de bloques o señal y errores del reconocedor. Rota al llegar a 256 KiB y conserva una copia anterior. El medidor de **Ajustes de voz** muestra el nivel relativo y la ruta efectiva. **Probar micrófono** mide la entrada elegida durante cinco segundos sin ejecutar órdenes.

## Pruebas automatizadas

- `python -m unittest -v test_commands test_resident test_voice test_audio_input` comprueba comandos, bandeja, preferencias, reintento ante desconexión simulada, tratamiento de baja confianza y exclusión del audio durante la respuesta. Con los modelos y dependencias instalados, también procesa audio sintético. Las pruebas de captura simulan formatos rechazados, 48 kHz estéreo, flujo silencioso, alternativas entre APIs y un cambio del predeterminado. En Windows también se comprueban las consultas nativas de endpoint y asignador.
- El diagnóstico del ejecutable abre las DLL y usa los modelos empaquetados para reconocer «Jarvis, abre Spotify» de corrido y con pausa. También comprueba una orden sin activación, el tiempo de espera, la enumeración de dispositivos y la síntesis en memoria, sin accionar Spotify ni usar un micrófono físico.
- `python -m unittest -v test_update_windows` comprueba el reinicio del ejecutable y la recuperación ante un arranque fallido. Requiere `dist/JARVIS.exe`.

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
| Con los altavoces activos, pide «Jarvis, ayuda» y después prueba tu volumen de respuesta habitual. | JARVIS habla una vez y vuelve a espera sin activarse por su propia voz. |
| Selecciona **Realtek**, habla durante **Probar micrófono** y repite con **Predeterminado de Windows**. | El medidor se mueve al hablar. Anota el backend y la frecuencia que muestra el resultado. |
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
