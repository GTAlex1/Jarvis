# JARVIS para Windows

Asistente gráfico que organiza ventanas entre monitores con órdenes en español. La interfaz tiene un núcleo animado, un historial de respuestas y accesos a **Aplicaciones**, **Pantallas**, **Ventanas** y **Ayuda**.

## Descargar y abrir

1. Descarga `JARVIS.exe` desde [GitHub Releases](https://github.com/GTAlex1/Jarvis/releases/latest).
2. Abre el ejecutable desde una carpeta en la que puedas guardar archivos.
3. Con VS Code abierto, escribe `VSCode izquierda` y pulsa **Intro**.

## Actualizaciones

JARVIS comprueba GitHub Releases al arrancar. Si hay una versión nueva, pulsa **Actualizar y reiniciar** y confirma el reinicio. La descarga se verifica con SHA-256 antes de sustituir el ejecutable. El actualizador se incluye desde la versión 0.3.0. Desde 0.4.1 espera a que Windows libere el ejecutable y confirma que la interfaz nueva está lista antes de borrar la copia de recuperación. Si falla, guarda el paso y el error en `%LOCALAPPDATA%/JARVIS/actualizacion.log`.

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

Para dictar, abre la consola con `python jarvis.py`, pulsa Intro con la línea vacía y confirma con `s`. El dictado requiere un motor de reconocimiento de voz en español compatible con System.Speech.

Consulta la [wiki](https://github.com/GTAlex1/Jarvis/wiki) y la [guía de desarrollo](Guia.md).
