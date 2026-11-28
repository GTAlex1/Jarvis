# Guía de JARVIS

## Ejecutable de Windows

GitHub Actions compila `jarvis_gui.py` con PyInstaller y comprueba en Windows el arranque, la bandeja, la instancia única, los motores de voz dentro del ejecutable y la sustitución y recuperación del archivo anterior. El flujo también comprueba el límite de descarga del actualizador y publica la wiki y la versión después de las pruebas. El resultado se adjunta como `JARVIS-Windows-x64` a la ejecución. Puedes abrir la [última compilación](https://github.com/GTAlex1/Jarvis/actions/workflows/windows.yml) desde el repositorio.

## Ciclo de vida del asistente

- `assistant.py` ofrece la ejecución de comandos en serie. Un futuro origen de entrada puede enviar texto mediante `Assistant.submit()` y recibir el resultado sin depender del panel.
- `resident.py` coordina la sesión de escritorio, las preferencias y el actualizador. El panel de `jarvis_gui.py` se crea al abrirlo por primera vez.
- `windows_tray.py` registra el icono con Win32. Un mutex por sesión de Windows limita JARVIS a una instancia. Una segunda apertura manual solo pide mostrar el panel existente. La bandeja recupera el icono al reiniciarse Explorer.
- `preferences.py` guarda la preferencia del micrófono y administra el inicio de sesión en el registro del usuario. `--background` inicia JARVIS en la bandeja. Para probarlo desde el código usa `python jarvis_gui.py --background`.

Los comandos y la consulta de actualizaciones se completan en segundo plano. El panel procesa los eventos de la bandeja y los resultados mediante una cola y suspende la animación al ocultarse. La consola recibe órdenes por teclado. La captura de voz de escritorio pasa por el servicio de la bandeja y su verificador.

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

Se eligió un detector pequeño para la espera y un transcriptor separado para la orden. System.Speech se utiliza para la síntesis. La verificación del hablante usa el modelo x-vector de Vosk. El ejecutable integra un transcriptor español para la escucha permanente. Los motores de voz pueden funcionar sin servicios externos.

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

## Captura en llamadas

En 0.6.3, Automática podía recurrir a ASIO y WASAPI usaba bloques de captura de tamaño fijo. Se reprodujo esa selección en pruebas con controladores simulados. En 0.6.4, WASAPI solicita modo compartido explícito y deja el tamaño de búfer al controlador. Si el formato supera los 96 kHz, intenta primero formatos de voz con conversión compartida. MME y DirectSound conservan sus búferes de compatibilidad. ASIO queda disponible con selección explícita. Se registra si el controlador pierde bloques.

El filtro de paso alto del flujo local atenúa corriente continua y ruido grave. Para el eco de las respuestas se mantiene el bloqueo del reconocedor de órdenes durante la síntesis, el descarte de bloques y el margen al reanudar. Una cancelación acústica completa necesita una referencia de reproducción sincronizada que el conjunto actual de WASAPI, MME y DirectSound no proporciona de forma uniforme. Los auriculares Bluetooth clásicos también pueden cambiar de perfil al abrir el micrófono. La causa específica de la distorsión en una llamada requiere comparar el mismo equipo con JARVIS apagado y encendido. [Modo compartido de Windows](https://learn.microsoft.com/windows/win32/coreaudio/exclusive-mode-streams) · [Audio Bluetooth clásico](https://learn.microsoft.com/es-es/windows-hardware/drivers/bluetooth/bluetooth-classic-audio)

## Verificación del hablante en 0.6.4

Vosk usa el modelo local `vosk-model-spk-0.4` de 13 MiB aproximadamente, distribuido bajo Apache 2.0. Cada perfil necesita tres muestras coherentes. Se comparan las dos mejores similitudes de coseno por perfil y se exige margen entre perfiles. El valor predeterminado 72/100 es operativo, no una tasa biométrica certificada. La duración y la calidad de tu voz se comprueban físicamente. Una activación breve puede armar la escucha, con ejecución bloqueada hasta verificar la orden. Cada turno de una conversación debe corresponder al mismo perfil confirmado.

Se guarda en `%LOCALAPPDATA%\JARVIS\perfiles-voz.dat` una lista versionada de firmas, cifrada e íntegra con DPAPI para el usuario actual. En 0.6.4 se bloqueaba la ejecución si no había perfiles válidos y se exigía un código local para las operaciones sensibles. Consulta [la revisión 0.6.4.1](#bug-064-001-y-validación-de-0641) para conocer las opciones actuales. La ventana concreta se revalida al ejecutar. El audio de enrolamiento permanece en memoria.

La firma de voz admite falsos rechazos y falsos positivos, especialmente ante reproducciones, imitaciones y síntesis. La confirmación local es independiente de la voz. [Modelo de hablantes de Vosk](https://alphacephei.com/vosk/models) · [DPAPI](https://learn.microsoft.com/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

## Elección del reconocimiento

| Motor | Evaluación para esta versión |
| --- | --- |
| Vosk + PocketSphinx | Conserva el flujo incremental en español ya empaquetado. Se verificaron órdenes sintéticas a 16 y 192 kHz y la extracción x-vector en CPU. La normalización y las sugerencias fonéticas operan sobre el catálogo de Windows. |
| Whisper con whisper.cpp | Admite inferencia en CPU, cuantización y modelos multilingües. Tiny Q5 ocupa alrededor de 31 MiB solo en pesos. Sumado a los motores actuales y al modelo de voz supera el límite de los actualizadores antiguos y requiere medir latencia en equipos de referencia. |
| sherpa-onnx | Ofrece alternativas multilingües locales y de flujo incremental. Incorporar el runtime y un modelo español requiere validar licencias, empaquetado, consumo y calidad antes de sustituir el flujo existente. |

Se mantiene Vosk para esta versión. La comparación de alternativas se hizo por capacidades y tamaño de distribución. Las pruebas de precisión con audio del proyecto se ejecutaron en Vosk. [Whisper.cpp](https://github.com/ggml-org/whisper.cpp) · [Pesos cuantizados](https://huggingface.co/ggerganov/whisper.cpp) · [Sherpa ONNX](https://k2-fsa.github.io/sherpa/onnx/nemo/nemotron-streaming.html)

La normalización, la comparación fonética, el diálogo y la similitud biométrica son módulos independientes del sistema operativo. Windows aporta su catálogo, la captura, DPAPI y el control del escritorio. La palabra de activación tiene un nombre centralizado y recursos propios como base para una configuración futura.

## Pruebas automatizadas

- `python -m unittest -v test_commands test_resident test_voice test_audio_input test_dialogue test_security` comprueba comandos, bandeja, preferencias, reintento ante desconexión simulada, tratamiento de baja confianza y exclusión del audio durante la respuesta. Con los modelos y dependencias instalados, también procesa audio sintético. Las pruebas de captura simulan formatos rechazados, 48 kHz estéreo, flujo silencioso, alternativas entre APIs y un cambio del predeterminado. También comprueba filtrado y decimación de 192 kHz, continuidad a 44,1 kHz, migración de interfaces, transcripción en directo y cambio de ruta ante fallos de reconocimiento. En Windows se comprueban las consultas nativas de endpoint y asignador. Las pruebas de conversación cubren la lectura por partes, el seguimiento, la expiración, la repetición, la cancelación y las aclaraciones sin panel. Los formatos alternativos de WASAPI y la pérdida de una interfaz guardada se prueban con controladores simulados.
- El diagnóstico del ejecutable abre las DLL y usa los modelos empaquetados para reconocer «Jarvis, abre Spotify» de corrido y con pausa. También comprueba una orden sin activación, el tiempo de espera, la enumeración de dispositivos y la síntesis en memoria, y reconoce una orden sintética capturada a 192 kHz con un tono fuera de banda añadido. El diagnóstico también verifica una orden sintética de seguimiento sin palabra de activación y que la gramática de síntesis admite «Jarvis, para» e ignora una orden normal. El diagnóstico usa audio sintético y no acciona Spotify. También extrae firmas de dos sintetizadores de prueba y comprueba que el comparador distinga las muestras seleccionadas. Las pruebas de Windows verifican DPAPI, migración, revocación y aprobación local simulada.
- `python -m unittest -v test_update_windows` comprueba el reinicio del ejecutable y la recuperación ante un arranque fallido. Requiere `dist/JARVIS.exe`. En CI también sustituye el ejecutable publicado de 0.4.1 usando el mecanismo de esa versión y comprueba el arranque de 0.6.4.

Desde un checkout del proyecto, puedes ejecutar el mismo diagnóstico del binario:

```powershell
Start-Process .\dist\JARVIS.exe -ArgumentList '--diagnostico-voz', 'tests/voice', 'diagnostico-voz.json' -Wait
Get-Content diagnostico-voz.json -Encoding UTF8
```

## Pruebas con tu micrófono

Antes de probar órdenes, registra tres muestras en **Perfiles de voz**. Haz las pruebas de llamadas y de voces ajenas con tus ajustes habituales.

| Prueba manual | Resultado esperado |
| --- | --- |
| Selecciona tu micrófono, activa la escucha permanente y cierra el panel con la X. Di «Jarvis, abre Spotify» de corrido. | Spotify se abre y JARVIS responde con el panel oculto. |
| Di «Jarvis», espera un segundo y di «abre la calculadora». Repite dejando pasar más de seis segundos. | La primera orden se ejecuta. La segunda necesita volver a decir «Jarvis». |
| Con el panel oculto, pide «Jarvis, ayuda», di «ventanas» y luego «sí», «repite» y «no». | JARVIS da ayuda hablada, conserva el tema y termina la conversación. |
| En **Estricto**, con dos ventanas del mismo programa abiertas, pide «Jarvis, cierra Firefox» y di «Me refiero a la opción dos» cuando enumere las opciones. Abre **Confirmar acción de voz** en la bandeja e introduce el código. | La ventana anunciada permanece abierta hasta la confirmación local. Después recibe la solicitud normal de cierre. |
| Con tus altavoces activos, interrumpe un tramo de una respuesta larga diciendo «Jarvis, para». Repite con el control de la bandeja. | La respuesta se corta y el altavoz no provoca órdenes de escritorio por realimentación. |
| En Discord y WhatsApp, compara la calidad de la voz con JARVIS pausado y activo. Repite con Automática, WASAPI y, si procede, MME y DirectSound. | Comprueba si la llamada reproduce distorsión y busca pérdidas de bloques en el registro. Repite si cambias de auricular o controlador. |
| Registra tres muestras propias y prueba órdenes de otra persona en la sala y desde una llamada. | JARVIS bloquea al hablante ajeno en la activación y durante una conversación. Comprueba también falsos rechazos de tu voz. |
| En **Estricto**, reproduce una grabación o voz sintética de prueba y solicita una operación sensible. | La operación solo puede ejecutarse tras la confirmación local. Desmarca Micrófono para cancelar la escucha. |
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

## BUG-064-001 y validación de 0.6.4.1

La prueba física de 0.6.4 completó el registro y detectó «Jarvis», pero rechazó todas las órdenes del propietario. Las pruebas de llamadas, voces ajenas y comandos naturales quedaron bloqueadas. Se reprodujeron dos defectos del código: Vosk puede devolver texto sin firma cuando faltan fotogramas de habla según su alineación, y el antiguo flujo podía vetar una orden por la firma de «Jarvis» aislada. Ambos casos se confundían con una falta de coincidencia. El disparador exacto en el equipo del informante requiere repetir las pruebas.

Registro y órdenes usan ahora PCM mono a 16 kHz y el mismo extractor incremental. La firma de una orden suficiente se compara por separado. Si es breve, se permite usar el comienzo de la misma intervención solo con continuidad acústica y actividad de voz suficiente en la orden. Una pausa impide incorporar la activación. Cada turno se vuelve a verificar. Si un turno sale demasiado corto, repite la orden completa con una frase más larga, por ejemplo «Dime cómo puedes ayudarme» o «Sí, confirma la orden». Se conserva el umbral guardado y el formato cifrado de los perfiles de 0.6.4.

**Perfiles de voz** distingue silencio, ruido, saturación, falta de duración y fallos de perfil o del verificador. Selecciona una fila para repetir una muestra. Después de las tres muestras, **Comprobar registro** pide una cuarta frase. Para un perfil existente, selecciónalo y pulsa **Probar perfil seleccionado**. El diagnóstico JSON incluye versión, interfaz, formato, métricas de calidad y estado del perfil. Los resultados de política se registran por categoría en `voz.log`.

### Confirmaciones y compatibilidad

Las reglas de [Seguridad y permisos](README.md#seguridad-y-permisos) se aplican a órdenes de voz. Una confirmación ocupa una única solicitud durante 25 segundos como máximo. La aprobación verbal también está sujeta al tiempo de seguimiento y, si la biometría está activa, a la comprobación del hablante. Cambiar los ajustes o perfiles, pausar la escucha y cancelar revoca las solicitudes pendientes. Cualquiera puede pronunciar una cancelación de alta confianza durante una operación pendiente, ya que solo impide ejecutarla.

Para apagar o reiniciar, JARVIS mantiene la cuenta atrás en la aplicación y luego solicita a Windows el cierre normal. Así evita la opción de cierre forzado asociada a una espera positiva del comando nativo. Windows conserva el control sobre los permisos y avisos de guardado. Windows Hello se evaluó. Se aplaza porque el cliente de escritorio necesita integrar y validar el adaptador WinRT para una ventana nativa, además de gestionar las configuraciones en las que Hello no está disponible. [Referencia de apagado de Windows](https://learn.microsoft.com/es-es/windows-server/administration/windows-commands/shutdown) · [Integración de verificación local](https://learn.microsoft.com/es-es/windows/win32/api/userconsentverifierinterop/nf-userconsentverifierinterop-iuserconsentverifierinterop-requestverificationforwindowasync)

El actualizador de 0.6.4 y anteriores solo analiza tres componentes. El primer salto a 0.6.4.1 requiere reemplazar el archivo con JARVIS cerrado. Los datos en el Registro y en `%LOCALAPPDATA%\JARVIS` se conservan. La revisión añade el descubrimiento de versiones de cuatro componentes para futuras actualizaciones.

### Comprobaciones de la revisión

- **Automatizadas.** Hay casos con audio sintético del mismo y de otro sintetizador, cortes breves, activación continua y con pausa, ruido, silencio y saturación. Windows comprueba DPAPI, perfil ilegible, políticas y caducidad, sustitución de los binarios de 0.4.1 y 0.6.4, y recuperación del ejecutable anterior. Las pruebas de apagado simulan la llamada al sistema.
- **Físicas pendientes.** Prueba primero el perfil conservado con «Jarvis, ayuda» y con una orden larga, seguida de «sí» o «repite». Compara una sola frase con una activación seguida de pausa. Si falla, prueba o renueva el perfil en la misma interfaz de audio y exporta el diagnóstico.
- **Físicas pendientes.** En Libertad con biometría activa, cierra una ventana de prueba, captura toda la pantalla y cancela una cuenta atrás de reinicio. Comprueba que una persona presente, otra en una llamada y una grabación no causen operaciones imprevistas. La biometría sigue admitiendo falsos positivos y negativos.
- **Físicas pendientes.** Compara la distorsión con JARVIS activo y pausado durante llamadas de Discord y WhatsApp en MME, DirectSound y WASAPI. Comprueba los nombres en inglés y las órdenes naturales una vez superado el bloqueo biométrico.

## Activación y reconocimiento en 0.6.4.2

El informe físico de 0.6.4.1 tuvo 14 comprobaciones correctas, cinco parciales, dos fallidas y una pendiente. El propietario validó la persistencia de perfiles y la coexistencia con Discord y WhatsApp en su equipo. Quedaron fallos al hablar sin pausa, falsos disparos durante conversaciones y dudas sobre voces ajenas. La prueba aislada del perfil quedó pendiente.

El corpus anterior combinaba una activación sintética inglesa y una orden española. El detector anterior falló en varias activaciones sintetizadas en español y se disparó al oír «Jarvis» en mitad de una de las frases de prueba. También elegía el final más tardío al encontrar varias pronunciaciones, dejando únicamente 25 ms de contexto antes del corte. Se separó el detector acústico en `wake_word.py`, se retiró una entrada amplia del diccionario, se introdujo la comprobación de actividad al principio de la frase y se corroboran los candidatos acústicos alternativos con Vosk. Si la transcripción general falla, una gramática secundaria que exige oír «Jarvis» puede recuperar dos órdenes acotadas: pedir ayuda y abrir la calculadora. Incluye opciones competidoras de negación. Las acciones sensibles requieren una intención explícita de alta confianza.

El mismo texto puede tener varias intenciones según su verbo, destino y contexto. La normalización admite clíticos y variantes peninsulares y latinoamericanas, y descarta negaciones, citas y condiciones reconocidas. La lista de programas cuenta identidades de aplicación, de modo que dos entradas equivalentes no abren un diálogo. Una coincidencia aproximada aislada se pregunta por su nombre. Los alias aprendidos son correcciones explícitas en una ventana local.

La voz de una persona puede activar la transcripción sin superar la biometría. El extractor usa el tramo de las palabras reconocidas y vuelve a verificar cada turno. Solo una consulta de ayuda puede aprovechar audio continuo de la activación cuando su propia muestra es corta. Se conservan el umbral, los cuatro perfiles de seguridad y los datos cifrados. Las grabaciones, imitaciones y voz sintética siguen fuera del alcance de una garantía de identidad. Un registro que indica «solicitada a Windows» acredita el envío de la operación; verificar el inicio real de videojuegos corresponde a 0.6.5.

El diagnóstico desde **Perfiles de voz** exporta los últimos eventos de señal, activación o continuación, transcripción, hablante, intención, permisos y resultado. Incluye estados y datos técnicos sin guardar texto, voz, firmas, identidad ni credenciales en el archivo exportado. En espera se conserva un búfer corto en memoria. Durante la respuesta solo se atienden interrupciones y se descarta el audio residual antes de volver a escuchar.

### Evaluación de motores y rendimiento

| Motor | Evaluación |
| --- | --- |
| PocketSphinx + VAD, Vosk y x-vector | Se mantienen. Funcionan en CPU y sin conexión. El modelo español pequeño ocupa aproximadamente 39 MB comprimidos y el hablante unos 13 MiB. Se conservan las firmas existentes. La segunda comprobación se ejecuta cuando hay un candidato acústico alternativo y el rescate léxico es puntual. |
| openWakeWord | Detector dedicado con ONNX en Windows. Su modelo publicado apunta a «hey jarvis» en inglés. El código es Apache 2.0 y los modelos incluidos tienen licencia CC BY-NC-SA 4.0. Entrenar y validar «Jarvis» en español, «Nexora» o una palabra personalizada requiere datos con permisos adecuados. |
| Whisper, whisper.cpp y faster-whisper | Whisper y whisper.cpp tienen distribución MIT. whisper.cpp ofrece CPU y pesos cuantizados. Se midió faster-whisper Tiny multilingüe con CTranslate2 en CPU int8 y dos hilos. Su archivo de pesos de prueba ocupa 75,5 MB adicionales y no se incorpora al ejecutable. Se podrán evaluar modelos mayores o inferencia puntual con voces reales en un equipo de referencia. |
| SpeechBrain ECAPA | El modelo publicado es Apache 2.0, entrenado con VoxCeleb y con PyTorch como dependencia en su integración habitual. Requeriría calibrar con llamadas, acentos y órdenes cortas y migrar las firmas. Se evaluó por documentación y empaquetado. |

Fuentes de modelos y licencias. [Vosk](https://alphacephei.com/vosk/models) · [openWakeWord](https://github.com/dscripka/openWakeWord) · [Whisper](https://github.com/openai/whisper) · [whisper.cpp](https://github.com/ggml-org/whisper.cpp) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [SpeechBrain ECAPA](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb)

Medición reproducible con `python benchmark_voice.py` y `--source` para el código de 0.6.4.1. Son diez casos sintéticos y una pasada en Linux sobre AMD EPYC 9V74 con Python 3.12. La latencia mide procesamiento fuera de tiempo real por clip. La CPU incluye el trabajo de todos los hilos. La RAM es el pico del proceso. La prueba de reposo alimenta 60 segundos de silencio al detector, sin micrófono ni audio simultáneo. Ninguna de las tres configuraciones usa GPU.

| Configuración | Casos correctos | Mediana por clip | CPU total del corpus | Pico de RAM | CPU del detector en 60 s de silencio |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.6.4.1 | 3/10 | 78 ms | 1.816 ms | 177,2 MiB | 372 ms |
| 0.6.4.2 | 8/10 | 575 ms | 5.351 ms | 183,4 MiB | 375 ms |
| faster-whisper Tiny, CPU int8 | 3/10 | 1.199 ms | 22.473 ms | 254,6 MiB | — |

El corpus incluye tres casos que no deben producir ninguna acción. faster-whisper se midió como alternativa que transcribe el enunciado completo y requiere que el nombre de activación aparezca al inicio del texto. La síntesis produjo sustituciones de ese nombre. Las cifras no son comparables con WER de producción ni sirven como tasa biométrica. Los dos casos pendientes del corpus revisado son órdenes de reinicio que la transcripción no entendió. El sistema las rechazó. La verificación física de rendimiento y precisión en Windows con micrófono real sigue pendiente.

### Versionado, canales y recuperación

Usa `mayor.menor.parche` o `mayor.menor.parche.revisión`. Las etiquetas preliminares usan `-alpha.N`, `-beta.N` y `-rc.N` con un número positivo. Para la misma base, Alpha precede a Beta, RC y la versión final. El canal estable busca etiquetas numéricas completas, el futuro canal beta podrá recibir Beta y RC, y desarrollo podrá recibir Alpha. El selector público de canales queda en el roadmap. Las versiones borrador y activos de otro formato se omiten.

0.6.4.2 se identifica como validación interna en las notas. Usa etiqueta numérica y el formato de publicación que el actualizador 0.6.4.1 ya sabe leer. No se marca como release principal de GitHub. Los clientes 0.6.4 y anteriores deberán reemplazar manualmente el ejecutable una sola vez con JARVIS cerrado. Después, **Actualizar y reiniciar** verifica la huella SHA-256 y el recibo de arranque. Si la versión llega a iniciarse pero el recibo es inválido o falta, el auxiliar cierra únicamente el proceso lanzado y restaura la copia anterior. El registro indica la ubicación de esa copia si Windows impide restaurarla.

### Comprobaciones físicas de 0.6.4.2

1. Actualiza desde 0.6.4.1 con **Actualizar y reiniciar**. Comprueba la versión, el dispositivo, el perfil de voz y Libertad con biometría activa.
2. Prueba el perfil seleccionado. Con el panel cerrado, di «Jarvis, ayuda» y «Jarvis, abre la calculadora» de corrido, con pausa y hablando con naturalidad. Repite una orden corta de seguimiento y una orden larga en días distintos.
3. Habla con otra persona con JARVIS activo durante varios minutos. Pídele que pruebe una orden segura por separado y que intente continuar una conversación iniciada por ti, en persona y por Discord. Prueba audio reproducido y revisa el diagnóstico aunque no se ejecute nada.
4. Prueba «Cerrá Spotify», «Ponme la calculadora», «Reiníciame el ordenador» y «No cierres Spotify». Si pruebas reinicio, guarda el trabajo y comprueba «cancela» durante la cuenta atrás. Añade, desactiva y borra un alias voluntario.
5. Conserva una prueba de llamada con Discord y WhatsApp con la escucha activa y pausada. Si tienes otros dispositivos, cambia entre WASAPI, MME, DirectSound y ASIO disponible, y comprueba USB, Bluetooth, analógico y el cambio de predeterminado mientras la aplicación está abierta. Anota formato, ruta y fase del fallo. Steam mantiene su comprobación física como control de 0.6.5.


## Catálogo de aplicaciones y juegos

En la candidata 0.6.5, **Aplicaciones** incluye entradas de Windows, clientes y carpetas portables. En la bandeja, **Carpetas de aplicaciones…** añade una carpeta local; si cancelas el selector, JARVIS ofrece borrar la lista adicional tras confirmación. Las carpetas habituales `PortableApps` y `Games` del usuario se consultan por defecto. Después de instalar, mover o eliminar un programa di o escribe `actualiza aplicaciones`. Un resultado que indique «sin ruta de arranque» puede necesitar un acceso directo creado desde el cliente del juego.

Una coincidencia aproximada se confirma diciendo el nombre, el número de la opción o «sí» si solo hay una propuesta. El panel y la consola permiten elegir por número. Para diferenciar ventanas del mismo programa puedes usar su título completo. Para distinguir instalaciones con el mismo nombre, puedes indicar también el proveedor. Algunos ejemplos son `abre Rocket League Epic Games`, `pon el honkai en la segunda pantalla`, `minimiza Discord` y `put VSCode on the left`. La captura y los modelos de voz son los de 0.6.4.2; el inglés escrito no implica reconocimiento acústico en inglés.

Para empezar a probar, consulta el [listado de órdenes](README.md#órdenes-de-windows) y los [detalles de fuentes y limitaciones](docs/catalogo-aplicaciones.md).

### Validación física de 0.6.5

1. Mantén una copia de 0.6.4.2. Abre el artefacto de la candidata y comprueba que conserva tu micrófono, biometría, perfil Libertad, arranque automático y uso simultáneo con Discord.
2. Prueba Valorant, Genshin Impact, Honkai: Star Rail, Rocket League por Epic y un juego de Steam. Si se abre la ficha del cliente, anota si JARVIS informa de que no pudo confirmar el arranque. Comprueba el juego real y registra si fue necesario pulsar **Jugar**.
3. Prueba Minecraft para Windows y, si está instalado, Minecraft Java; comprueba que el launcher y el juego se distinguen. Prueba también un título de EA, Ubisoft, Battle.net, GOG y Game Pass por cada cliente del que dispongas.
4. Añade una carpeta portable de otra unidad, lanza una aplicación y actualiza después de quitarla. Prueba dos ventanas de VS Code, los alias de Chrome/Edge y los movimientos a un segundo monitor. Comprueba el aviso de guardar al cerrar un documento editado.
5. Desde el panel oculto, prueba nombres y alias por voz, rechazos de hablantes ajenos y confirmaciones de acciones protegidas. Haz la comparación con 0.6.4.2 si reaparece un fallo físico.
