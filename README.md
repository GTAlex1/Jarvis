# JARVIS para Windows

Asistente residente para controlar ventanas, aplicaciones y otras funciones de Windows con órdenes escritas o de voz en español. La interfaz tiene un núcleo animado, un historial de respuestas y accesos a **Aplicaciones**, **Pantallas**, **Ventanas** y **Ayuda**.

## Descargar y abrir

1. Descarga `JARVIS.exe` desde [GitHub Releases](https://github.com/GTAlex1/Jarvis/releases/latest).
2. Guarda y abre el ejecutable desde una carpeta de tu usuario. Usa una ubicación fija si activas el inicio automático.
3. Con VS Code abierto, escribe `VSCode izquierda` y pulsa **Intro**.

## Bandeja del sistema

Desde la versión 0.5.0, la X oculta el panel y JARVIS sigue abierto en el área de notificación de Windows. Si no ves el icono, búscalo bajo la flecha junto al reloj. Abre el panel desde el icono o vuelve a ejecutar `JARVIS.exe` para recuperar la misma instancia.

- **Micrófono** permite bloquear toda escucha de JARVIS. **Escucha permanente** activa la palabra «Jarvis» y está desactivada por defecto.
- **Ajustes de voz…** permite elegir el micrófono, la voz instalada en Windows, el volumen y la sensibilidad. Los cambios se guardan para futuros arranques.
- **Iniciar con Windows** está desactivado por defecto. Al activarlo, JARVIS se abre en la bandeja cuando inicias sesión con tu cuenta, sin pedir permisos de administrador. Si cambias el ejecutable de carpeta, vuelve a activar la opción desde la nueva ubicación. También puedes gestionarla desde **Configuración → Aplicaciones → Inicio** de Windows.
- **Salir de JARVIS** cierra todo el programa. También puedes escribir `salir` en el panel.

La animación se detiene al ocultar o minimizar el panel.

## Usar JARVIS por voz

1. Abre **Perfiles de voz** desde la bandeja. Graba tres frases distintas en un entorno tranquilo, con permiso de la persona que habla, y guarda el perfil.
2. En **Ajustes de voz** elige el micrófono y activa **Escucha permanente**. Comprueba que **Micrófono** esté marcado en la bandeja.
3. Puedes cerrar el panel con la X. Di «Jarvis, abre Spotify» de corrido o con una pausa breve. JARVIS verifica la voz que pronuncia la orden. Si dices «Jarvis» por separado y la muestra es demasiado corta, la activación queda pendiente hasta verificar la frase siguiente.
4. Comprueba el estado en el panel o en el icono de la bandeja. Si un turno es demasiado breve para verificarlo, usa una frase más larga, como «Sí, continúa con la explicación».

Spotify y los nombres de juegos deben figurar entre las aplicaciones que Windows expone o las ventanas abiertas. JARVIS acepta variantes como «cerraré Spotify» y puede sugerir una coincidencia para «roquet lig» sin ejecutarla automáticamente.

### Perfiles y autorización

Desde **Perfiles de voz** puedes añadir, renombrar, renovar y eliminar perfiles. La exigencia de coincidencia se ajusta en **Ajustes de voz**. La captura de órdenes queda bloqueada sin perfiles válidos. El registro conserva firmas cifradas para la cuenta de Windows con DPAPI y procesa las muestras en memoria.

Para cerrar una ventana, bloquear Windows, capturar la pantalla, abrir herramientas administrativas o salir de JARVIS por voz, abre **Confirmar acción de voz** en la bandeja y escribe el código mostrado. El código es de un solo uso y caduca. Para detener la escucha y cancelar una solicitud pendiente, desmarca **Micrófono** o **Escucha permanente** en la bandeja. Los comandos escritos siguen disponibles.

La firma de voz es probabilística. Grabaciones, imitaciones o voces sintéticas pueden parecerse a un perfil y superar la verificación. La confirmación local protege las operaciones sensibles aun en ese caso.

### Conversar desde la bandeja

Di **«Jarvis, ayuda»** y, después de que te pregunte, responde **«ventanas»**. También puedes pedir **«aplicaciones»** y decir **«continúa»** para escuchar el siguiente grupo. **«Repite»** vuelve a leer la última respuesta y **«dame más detalles»** ofrece la siguiente parte cuando está disponible. **«Sí»** continúa una respuesta por partes. **«No»**, **«cancela»** y **«para»** cierran la conversación.

Cuando hay varias aplicaciones o ventanas con el mismo nombre, JARVIS pregunta cuál quieres. Responde con el número o con un nombre específico. JARVIS conserva la conversación en memoria y puede pedir aclaraciones o hablar aunque el panel esté oculto.

Por defecto, después de responder JARVIS te escucha durante **8 segundos** sin volver a decir «Jarvis» y conserva el contexto **25 segundos**. Pasado el primer plazo puedes usar «Jarvis, repite» mientras siga vigente el contexto. En **Ajustes de voz** puedes cambiar ambos plazos, elegir el detalle hablado o desactivar el modo conversacional. Para interrumpir mientras habla, di **«Jarvis, para»** o usa **Detener respuesta de voz** en la bandeja.

### Probar el reconocimiento

Elige un micrófono y una de las interfaces disponibles para ese dispositivo. **Automática** intenta MME y DirectSound antes que WASAPI cuando esas rutas están disponibles. También puede cambiar de ruta si la captura o el reconocimiento fallan. WASAPI usa captura compartida y el periodo del controlador. ASIO se ofrece si está disponible para la entrada y requiere elegirlo explícitamente.

Pulsa **Probar micrófono** y di «abre Spotify». La prueba distingue señal, actividad de voz y palabras reconocidas, y muestra la transcripción en directo. Si cambia la ruta del medidor, repite la frase. El registro técnico se guarda en `%LOCALAPPDATA%\JARVIS\voz.log`. El audio y la transcripción de la prueba se procesan en memoria.

## Actualizaciones

JARVIS comprueba GitHub Releases al arrancar. Si hay una versión nueva, pulsa **Actualizar y reiniciar** y confirma el reinicio. La descarga se verifica con SHA-256 antes de sustituir el ejecutable. El actualizador se incluye desde la versión 0.3.0. Para aplicar la actualización, JARVIS sale por completo, espera a que Windows libere el ejecutable y se vuelve a abrir. El actualizador conserva la copia anterior hasta que el nuevo arranque se confirma. Si falla, guarda el paso y el error en `%LOCALAPPDATA%/JARVIS/actualizacion.log`.

Para publicar una actualización, incrementa `VERSION` en `updater.py`. GitHub Actions compila y prueba la aplicación en Windows antes de publicar el ejecutable.

## Órdenes de Windows

| Función | Ejemplos |
| --- | --- |
| Abrir una aplicación | `abre VSCode`, `abre Chrome` |
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
| Captura | `captura de pantalla` abre el recorte de Windows para seleccionar una zona |
| Bloquear sesión | `bloquea el equipo` |
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
