# JARVIS para Windows

Asistente de escritorio que mueve ventanas entre monitores con órdenes en español. Puedes escribir las órdenes o dictarlas desde la terminal.

## Primer uso

1. Descarga o clona el repositorio en Windows 10 u 11.
2. Si necesitas Python, instala Python 3.10 o posterior desde [python.org](https://www.python.org/downloads/windows/), con Tcl/Tk y Python disponible en PATH.
3. Haz doble clic en `Abrir-Jarvis.cmd` o ejecuta `python jarvis_gui.py` desde PowerShell.
4. Con VS Code abierto, escribe esta orden en la ventana y pulsa Intro:

   > Mueve la pestaña VSCode a la mitad izquierda de la pantalla 1

Si PowerShell indica que `py` no existe, prueba `python --version`. Si muestra una versión compatible, puedes usar `python` directamente. Si tampoco está disponible, instala Python y vuelve a abrir PowerShell.

La consola sigue disponible con `python jarvis.py`.

## Comandos

| Orden | Resultado |
| --- | --- |
| `mueve la pestaña VSCode a la mitad izquierda de la pantalla 1` | Coloca la ventana completa de VS Code en la mitad izquierda. |
| `pon la ventana de Firefox a la mitad derecha del monitor 2` | Coloca Firefox en la mitad derecha del monitor 2. |
| `pantallas` | Muestra los identificadores de monitores detectados. |
| `ventanas` | Muestra los programas abiertos y los títulos de sus ventanas. |
| `ayuda` | Muestra los ejemplos disponibles. |
| `salir` | Cierra el asistente. |

Puedes decir «mueve Chrome a la izquierda» o «pon el Explorador a la derecha». JARVIS busca el nombre del programa, su ejecutable o el título de la ventana. Si hay varias coincidencias, usa un título más concreto de la lista de **Ventanas**.

Si omites el número de pantalla, JARVIS usa la principal. El cálculo respeta el área de trabajo para dejar sitio a la barra de tareas.

## Dictado

En la versión de consola, pulsa Intro con la línea vacía, di la orden y confirma la transcripción con `s`. Para dictar necesitas un micrófono y un motor de reconocimiento en español compatible con System.Speech en Windows PowerShell. Puedes escribir órdenes sin configurar el micrófono. El proyecto usa la biblioteca estándar de Python.

## Estado del proyecto

El prototipo mueve ventanas y muestra respuestas en su ventana o en la terminal. Las peticiones libres y las acciones encadenadas quedan para futuras versiones. Se verificó el análisis de órdenes y el cálculo geométrico en Linux. Queda pendiente validar el movimiento y el dictado en un equipo Windows.

Consulta la [guía de desarrollo](Guia.md) para resolver problemas o añadir comandos.
