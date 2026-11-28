# JARVIS para Windows

Asistente residente para controlar ventanas, aplicaciones y otras funciones de Windows con órdenes escritas o de voz en español. La interfaz tiene un núcleo animado, un historial de respuestas y accesos a **Aplicaciones**, **Pantallas**, **Ventanas** y **Ayuda**.

## Descargar y abrir

1. Descarga `JARVIS.exe` desde [GitHub Releases](https://github.com/GTAlex1/Jarvis/releases).
2. Guarda y abre el ejecutable desde una carpeta de tu usuario. Usa una ubicación fija si activas el inicio automático.
3. Con VS Code abierto, escribe `VSCode izquierda` y pulsa **Intro**.

## Bandeja del sistema

Desde la versión 0.5.0, la X oculta el panel y JARVIS sigue abierto en el área de notificación de Windows. Si no ves el icono, búscalo bajo la flecha junto al reloj. Abre el panel desde el icono o vuelve a ejecutar `JARVIS.exe` para recuperar la misma instancia.

- **Micrófono** permite bloquear toda escucha de JARVIS. **Escucha permanente** activa la palabra «Jarvis» y está desactivada por defecto.
- **Ajustes de voz…** permite elegir el micrófono, la voz instalada en Windows, el volumen y la sensibilidad. Los cambios se guardan para futuros arranques.
- **Iniciar con Windows** está desactivado por defecto. Al activarlo, JARVIS se abre en la bandeja cuando inicias sesión con tu cuenta, sin pedir permisos de administrador. Si cambias el ejecutable de carpeta, vuelve a activar la opción desde la nueva ubicación. También puedes gestionarla desde **Configuración → Aplicaciones → Inicio** de Windows.
- **Salir de JARVIS** cierra todo el programa. También puedes escribir `salir` en el panel.

Al cerrar el panel por primera vez, JARVIS avisa de que sigue en segundo plano. El icono cambia de expresión y color al esperar, escuchar, procesar, ejecutar, detectar un error o desactivar el micrófono. El menú permite cambiar la escucha, buscar actualizaciones, reiniciar y **Salir completamente**. [Vista previa y funcionamiento de la bandeja](docs/bandeja.md)

## Usar JARVIS por voz

1. Abre **Perfiles de voz** desde la bandeja. Graba tres frases distintas en un entorno tranquilo, con permiso de la persona que habla, y guarda el perfil.
2. En **Ajustes de voz** elige el micrófono y activa **Escucha permanente**. Comprueba que **Micrófono** esté marcado en la bandeja.
3. Puedes cerrar el panel con la X. Di «Jarvis, abre Spotify» de corrido o con una pausa breve. JARVIS verifica la voz que pronuncia la orden. Si dices «Jarvis» por separado y la muestra es demasiado corta, la activación queda pendiente hasta verificar la frase siguiente.
4. Comprueba el estado en el panel o en el icono de la bandeja. Si un turno es demasiado breve para verificarlo, usa una frase más larga, como «Sí, continúa con la explicación».

Puedes decir «Cerrá Spotify», «Ponme la calculadora» o «Reiníciame el ordenador». Las coincidencias exactas con una misma identidad de aplicación se abren directamente si lo permite tu perfil. Las coincidencias aproximadas se confirman.

### Idioma y nombres de aplicaciones

El modelo español sigue activo por defecto. Puedes pronunciar nombres extranjeros dentro de una orden española. JARVIS compara lo que oye con las aplicaciones descubiertas y pide confirmación ante coincidencias aproximadas. Para usar órdenes como «open Firefox» o «move VSCode to the left» en inglés, elige **Voz en inglés…** en la bandeja. La primera vez se descarga un modelo de 41 MB. [Reconocimiento local y límites](docs/reconocimiento-contextual.md)

### Adaptación de voz

Abre **Adaptación de voz** desde la bandeja. Añade la palabra que suele transcribir JARVIS y el nombre exacto de la aplicación. Por ejemplo, puedes asociar «es potify» a «Spotify». Usa **Guardar** para aplicar cambios, desmarca la opción para suspenderlos o usa **Restablecer** para borrarlos. Las asociaciones son locales y solo se guardan mediante esta ventana. Las reglas de biometría y permisos se aplican a la intención resultante.

### Perfiles de voz

Abre **Perfiles de voz** para consultar la calidad de cada muestra, repetir una grabación concreta o probar un perfil ya guardado. Completa las tres muestras y pulsa **Comprobar registro** para grabar una cuarta frase independiente antes de guardar. El resultado muestra si coincide y la puntuación frente al umbral de **Ajustes de voz**. Puedes renombrar, renovar y eliminar perfiles. Las firmas se cifran para la cuenta de Windows y el audio se procesa en memoria. **Exportar diagnóstico** guarda solo datos técnicos y de calidad.

### Seguridad y permisos

Abre esta opción desde el panel o la bandeja. **Verificar el hablante** es independiente del perfil de permisos.

| Perfil | Comportamiento |
| --- | --- |
| **Libertad** | Abre y cierra aplicaciones, gestiona ventanas, captura la pantalla y bloquea Windows por voz. Apagado y reinicio con diez segundos para cancelar. Las herramientas administrativas mantienen aprobación local. |
| **Equilibrado** | Predeterminado en instalaciones nuevas. Confirma verbalmente las acciones de riesgo intermedio y el apagado o reinicio. Exige aprobación local para las herramientas administrativas. |
| **Estricto** | Código temporal local para las acciones sensibles. Conserva la protección previa al actualizar una instalación con ajustes de voz guardados. |
| **Personalizado** | Elige por categoría entre permitir, confirmar por voz, botón, atajo **Ctrl + Alt + F10**, código y bloqueo. Las categorías críticas mantienen autorización local. |

Si quieres usar JARVIS a diario solo por voz, elige **Libertad** y mantén **Verificar el hablante** marcado. Cambiar a Libertad o desactivar la verificación exige aceptar el aviso local. Las llamadas y grabaciones pueden activar órdenes, y la biometría es probabilística. Di «cancela» para detener una acción pendiente, o desmarca **Micrófono** en la bandeja. Si un «sí» es demasiado breve para verificar, di «Sí, confirma la orden».

### Conversar desde la bandeja

Di **«Jarvis, ayuda»** y, después de que te pregunte, responde **«ventanas»**. También puedes pedir **«aplicaciones»** y decir **«continúa»** para escuchar el siguiente grupo. **«Repite»** vuelve a leer la última respuesta y **«dame más detalles»** ofrece la siguiente parte cuando está disponible. **«Sí»** continúa una respuesta por partes. **«No»**, **«cancela»** y **«para»** cierran la conversación.

Cuando hay varias aplicaciones o ventanas con el mismo nombre, JARVIS pregunta cuál quieres. Responde con el número o con un nombre específico. JARVIS conserva la conversación en memoria y puede pedir aclaraciones o hablar aunque el panel esté oculto.

Por defecto, después de responder JARVIS te escucha durante **8 segundos** sin volver a decir «Jarvis» y conserva el contexto **25 segundos**. Pasado el primer plazo puedes usar «Jarvis, repite» mientras siga vigente el contexto. En **Ajustes de voz** puedes cambiar ambos plazos, elegir el detalle hablado o desactivar el modo conversacional. Para interrumpir mientras habla, di **«Jarvis, para»** o usa **Detener respuesta de voz** en la bandeja.

### Probar el reconocimiento

Elige un micrófono y una de las interfaces disponibles para ese dispositivo. **Automática** intenta MME y DirectSound antes que WASAPI cuando esas rutas están disponibles. También puede cambiar de ruta si la captura o el reconocimiento fallan. WASAPI usa captura compartida y el periodo del controlador. ASIO se ofrece si está disponible para la entrada y requiere elegirlo explícitamente.

Pulsa **Probar micrófono** y di «abre Spotify». La prueba distingue señal, actividad de voz y palabras reconocidas, y muestra la transcripción en directo. Si cambia la ruta del medidor, repite la frase. El registro técnico se guarda en `%LOCALAPPDATA%\JARVIS\voz.log`. El audio y la transcripción de la prueba se procesan en memoria.

## Actualizaciones

**0.6.4.2 es una revisión experimental para validación interna.** Desde 0.6.4.1 puedes usar **Buscar actualizaciones** y **Actualizar y reiniciar**. Desde 0.6.4 o anterior, sal de JARVIS en la bandeja y reemplaza el ejecutable una sola vez por el de la [release de 0.6.4.2](https://github.com/GTAlex1/Jarvis/releases/tag/v0.6.4.2). Conserva el nombre y la carpeta si tienes configurado el inicio automático. Se conservan tus datos locales.

JARVIS comprueba GitHub Releases al arrancar. Si hay una versión nueva, pulsa **Actualizar y reiniciar** y confirma el reinicio. La descarga se verifica con SHA-256 antes de sustituir el ejecutable. El actualizador se incluye desde la versión 0.3.0. Para aplicar la actualización, JARVIS sale por completo, espera a que Windows libere el ejecutable y se vuelve a abrir. El actualizador conserva la copia anterior hasta que el nuevo arranque se confirma. Si falla, guarda el paso y el error en `%LOCALAPPDATA%/JARVIS/actualizacion.log`.

Para publicar una actualización, incrementa `VERSION` en `updater.py`. GitHub Actions compila y prueba la aplicación en Windows antes de publicar el ejecutable.

## Catálogo de aplicaciones y juegos

La candidata **0.6.5-rc.2** incorpora aplicaciones de Inicio, Microsoft Store, el escritorio, el registro y tus carpetas portables. El catálogo funciona en segundo plano, incluso con el panel oculto. Usa **Aplicaciones** para ver el catálogo, **Ventanas** para ver lo que está abierto y `actualiza aplicaciones` después de instalar o desinstalar algo. El catálogo incluye accesos PWA con identidad propia. Consulta el resultado posterior con «estado del arranque». Para añadir una carpeta de otro disco, usa **Añadir carpeta de aplicaciones…** en la bandeja.

Puedes probar `abre el visual`, `abre el navegador`, `pon el honkai en la segunda pantalla` o `open the calculator` con los nombres y alias que ofrezca tu instalación. JARVIS te pedirá elegir si hay varios destinos o si reconoce un nombre aproximado. Los launchers pueden requerir sesión, actualización o pulsar **Jugar**. JARVIS distingue entre solicitar el arranque y observar el juego abierto.

Consulta la [cobertura por proveedor](docs/catalogo-aplicaciones.md), la [guía de comprobaciones físicas](Guia.md#validación-física-de-065) y el [listado de órdenes](#órdenes-de-windows).

## Órdenes de Windows

| Función | Ejemplos |
| --- | --- |
| Abrir una aplicación o juego | `abre VSCode`, `abre Chrome` |
| Ver el último arranque | «estado del arranque» o «launch status» |\n| Ver y actualizar el catálogo | `aplicaciones`, `actualiza aplicaciones`; `ventanas` muestra lo que está abierto |
| Cerrar una ventana | `cierra Chrome`, `cierra el Bloc de notas` |
| Minimizar y restaurar | `minimiza Chrome`, `restaura Firefox` |
| Primer plano | `enfoca Spotify`, `activa VSCode` |
| Maximizar y centrar | `maximiza VSCode`, `centra el Explorador` |
| Mitades | `Chrome izquierda`, `Firefox derecha`, `VSCode arriba`, `VSCode abajo` |
| Esquinas | `Chrome esquina superior izquierda`, `Chrome arriba derecha`, `VSCode abajo izquierda`, `VSCode esquina inferior derecha` |
| Cambiar de monitor | `mueve VSCode a la pantalla 2` |
| Posición en otro monitor | `Chrome esquina superior derecha monitor 2`, `Firefox centro pantalla principal` |
| Pantalla completa | `Visual Studio Code pantalla completa` |
| Abrir herramientas | `abre configuración`, `abre administrador de tareas`, `abre calculadora`, `abre explorador` |
| Abrir carpetas | `abre descargas`, `abre documentos`, `abre imágenes`, `abre papelera` |
| Ajustes de Windows | `abre configuración de pantalla`, `abre configuración de sonido`, `abre wifi`, `abre bluetooth`, `abre windows update` |
| Escritorio y tareas | `escritorio`, `vista de tareas`, `minimiza todo`, `restaura todas las ventanas` |
| Captura | `captura de pantalla` abre el recorte. `captura toda la pantalla` usa el atajo de guardado de Windows |
| Bloquear sesión | `bloquea el equipo` |
| Energía | `apaga el equipo`, `reinicia el equipo`, `cancela` durante la cuenta atrás |
| Volumen | `sube volumen`, `baja volumen`, `silencia o activa el sonido` |
| Música | `reproducir o pausar`, `siguiente canción`, `anterior canción` |
| Consultar y salir | `ventanas`, `aplicaciones`, `pantallas`, `ayuda`, `salir` |

JARVIS reconoce `VSCode`, `VS Code` y `Visual Studio Code`, además de títulos de ventanas y nombres de ejecutables. Conserva las frases largas y la corrección de `izquieda`.

Si hay varias coincidencias para cerrar, mover, restaurar o enfocar, JARVIS pide un título más específico. Minimizar un programa minimiza sus ventanas coincidentes. El cierre utiliza la solicitud normal de Windows y la aplicación puede preguntar si quieres guardar.

Las posiciones respetan el área de trabajo y usan la pantalla principal cuando omites el monitor. Las cuatro esquinas ocupan un cuarto del área. Centrar conserva el tamaño mientras que cambiar de monitor ajusta las ventanas demasiado grandes. Una ventana maximizada conserva ese estado al cambiar de monitor. «Pantalla completa» maximiza la ventana.

Escritorio, silencio y reproducción alternan su estado igual que sus teclas de Windows. El volumen cambia un paso por orden. Windows puede impedir enfocar una ventana o controlar una aplicación elevada. JARVIS muestra el resultado de la operación.

Abrir aplicaciones utiliza las entradas del menú Inicio. El botón **Aplicaciones** lista los nombres disponibles. Las aplicaciones portátiles sin entrada en Inicio pueden quedar fuera de la lista.

## Ejecutar desde el código fuente

En Windows 10 u 11, instala [Python 3.10 o posterior](https://www.python.org/downloads/windows/) con Tcl/Tk. Ejecuta `python jarvis_gui.py` o haz doble clic en `Abrir-Jarvis.cmd`. Si alguno de los comandos `py` o `python` falta, el lanzador prueba el otro.

Para usar la escucha permanente desde el código, instala las dependencias y prepara el modelo antes de iniciar el panel. La versión empaquetada se compila con Python 3.12 x64.

```powershell
python -m pip install -r requirements-voice.txt
python prepare_voice_model.py
python jarvis_gui.py
```

Para usar la consola por teclado, sal de la aplicación de bandeja y ejecuta `python jarvis.py`. La entrada de voz se gestiona desde la aplicación de bandeja y utiliza los perfiles autorizados.

Las pruebas que requieren tu equipo están en la [lista de comprobación manual](Guia.md#pruebas-con-tu-micrófono). Consulta la [wiki](https://github.com/GTAlex1/Jarvis/wiki) y la [guía de desarrollo](Guia.md).


## Distribución y desarrollo

El ejecutable incluye las dependencias y los modelos esenciales. El reconocimiento y los comandos funcionan localmente en CPU. Consulta los [requisitos del proyecto](AGENTS.md) y la [hoja de ruta](ROADMAP.md) y el [historial de cambios](CHANGELOG.md).
