# JARVIS para Windows

Asistente gráfico que organiza ventanas entre monitores con órdenes en español. La interfaz tiene un núcleo animado, un historial de respuestas y accesos a **Aplicaciones**, **Pantallas**, **Ventanas** y **Ayuda**.

## Descargar y abrir

1. Abre [Aplicación de Windows](https://github.com/GTAlex1/Jarvis/actions/workflows/windows.yml) con tu sesión de GitHub iniciada. En la última ejecución correcta, descarga **JARVIS-Windows-x64** desde **Artifacts**.
2. Extrae el ZIP y abre `JARVIS.exe`. El ejecutable incluye Python.
3. Con VS Code abierto, escribe `VSCode izquierda` y pulsa **Intro**.

## Órdenes

| Orden | Resultado |
| --- | --- |
| `abre VSCode` | Busca Visual Studio Code en el menú Inicio y solicita a Windows que lo abra. |
| `minimiza Chrome` | Minimiza las ventanas abiertas de Chrome. |
| `aplicaciones` | Lista las aplicaciones que Windows ofrece en el menú Inicio. |
| `VSCode izquierda` | Coloca VS Code en la mitad izquierda. |
| `vscode izquieda` | Interpreta la errata «izquieda» como «izquierda». |
| `Visual Studio Code pantalla completa` | Maximiza VS Code. |
| `Chrome derecha monitor 2` | Coloca Chrome en la mitad derecha del monitor 2. |
| `maximiza el Explorador en la pantalla 2` | Maximiza el Explorador en el monitor 2. |
| `pantallas` | Lista los identificadores de monitores. |
| `ventanas` | Lista los programas y los títulos de sus ventanas visibles. |
| `ayuda` | Muestra ejemplos. |
| `salir` | Cierra JARVIS. |

También puedes escribir frases completas como «mueve la pestaña VSCode a la mitad izquierda de la pantalla 1». JARVIS busca por nombre del programa, ejecutable o título. Si hay varias coincidencias, escribe una parte más específica del título. Si omites el monitor, se usa el principal. «Pantalla completa» maximiza la ventana dentro del escritorio de Windows.

Para abrir una aplicación cerrada, JARVIS usa el menú Inicio de Windows. Si aparecen varios resultados, indica el nombre completo. Las aplicaciones portátiles sin entrada en Inicio pueden quedar fuera de la lista.

## Ejecutar desde el código fuente

En Windows 10 u 11, instala [Python 3.10 o posterior](https://www.python.org/downloads/windows/) con Tcl/Tk. Ejecuta `python jarvis_gui.py` o haz doble clic en `Abrir-Jarvis.cmd`. Si alguno de los comandos `py` o `python` falta, el lanzador prueba el otro.

Para dictar, abre la consola con `python jarvis.py`, pulsa Intro con la línea vacía y confirma con `s`. El dictado requiere un motor de reconocimiento de voz en español compatible con System.Speech.

Consulta la [wiki](https://github.com/GTAlex1/Jarvis/wiki) y la [guía de desarrollo](Guia.md).
