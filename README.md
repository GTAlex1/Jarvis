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

1. Abre **Ajustes de voz** en el panel o en la bandeja. Elige el micrófono y activa **Escucha permanente**. El interruptor **Micrófono** de la bandeja debe estar marcado.
2. Puedes cerrar el panel con la X. Di **«Jarvis, abre Spotify»** de corrido, o di **«Jarvis»**, haz una pausa y luego da la orden. Spotify debe aparecer en el menú Inicio para que JARVIS pueda abrirlo.
3. JARVIS dispone de hasta **6 segundos** tras la activación para reconocer la orden. El panel muestra el estado de voz y el icono de la bandeja lo indica al pasar el ratón.
4. Después de ejecutar la orden, JARVIS responde con la voz elegida y vuelve a esperar. El **volumen 0** silencia las respuestas. Con **Automática**, prioriza las voces en español disponibles en el motor clásico de Windows.

La detección y el reconocimiento funcionan en el equipo. El ejecutable incluye los modelos y puede usarlos sin conexión ni claves. JARVIS procesa el audio en memoria, descarta la entrada durante su propia respuesta y guarda las preferencias de voz en tu cuenta de Windows. El historial del panel muestra texto durante la sesión.

### Probar el reconocimiento en 0.6.2

En **Ajustes de voz**, elige **Predeterminado de Windows** o un micrófono físico. En **Interfaz de captura** puedes elegir **Automática**, **MME**, **DirectSound** o **WASAPI**. El micrófono aparece una vez aunque Windows lo exponga mediante varias interfaces. Con el dispositivo predeterminado y MME se puede usar el asignador de sonido de Windows. Con DirectSound se puede usar su controlador primario.

Pulsa **Probar micrófono** y di «abre Spotify». La prueba muestra por separado **Señal recibida**, **Voz detectada** y **Palabras reconocidas**, con transcripción en directo. Con **Automática**, si falla la prueba de reconocimiento, JARVIS puede pasar a otra ruta. Repite la frase cuando cambie la interfaz que muestra el medidor. La prueba dura unos cinco segundos por ruta y las palabras aparecen durante la sesión de prueba.

Cuando una ruta funciona en la prueba automática, JARVIS la prioriza durante esa sesión. Puedes guardar una interfaz concreta para próximos arranques. El registro `%LOCALAPPDATA%\JARVIS\voz.log` guarda detalles técnicos de la captura y el reconocimiento. La transcripción y el audio de la prueba se procesan en memoria.

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

Para el dictado manual de consola, sal de la aplicación de bandeja y ejecuta `python jarvis.py`. Con **Micrófono** habilitado, pulsa Intro con la línea vacía y confirma con `s`. El dictado requiere un motor de reconocimiento de voz en español compatible con System.Speech.

Las pruebas que requieren tu equipo están en la [lista de comprobación manual](Guia.md#pruebas-con-tu-micrófono). Consulta la [wiki](https://github.com/GTAlex1/Jarvis/wiki) y la [guía de desarrollo](Guia.md).


## Distribución y desarrollo

El ejecutable incluye las dependencias y los modelos esenciales. El reconocimiento y los comandos funcionan localmente en CPU. Consulta los [requisitos del proyecto](AGENTS.md) y la [hoja de ruta](ROADMAP.md).
