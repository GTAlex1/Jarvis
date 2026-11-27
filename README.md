# JARVIS para Windows

Asistente de escritorio que mueve ventanas entre monitores con órdenes en español. Puedes escribir las órdenes o dictarlas desde la terminal.

## Primer uso

1. Descarga o clona este repositorio.
2. Abre una terminal en la carpeta y ejecuta `py jarvis.py` en Windows 10 u 11 con Python 3.10 o posterior.
3. Abre VS Code y prueba esta orden:

   > Mueve la pestaña VSCode a la mitad izquierda de la pantalla 1

## Comandos

| Orden | Resultado |
| --- | --- |
| `mueve la pestaña VSCode a la mitad izquierda de la pantalla 1` | Coloca la ventana completa de VS Code en la mitad izquierda. |
| `pon la ventana de Firefox a la mitad derecha del monitor 2` | Coloca Firefox en la mitad derecha del monitor 2. |
| `pantallas` | Muestra los identificadores de monitores detectados. |
| `ventanas` | Muestra los títulos de las ventanas visibles. |
| `ayuda` | Muestra los ejemplos disponibles. |
| `salir` | Cierra el asistente. |

Si omites el número de pantalla, JARVIS usa la principal. El cálculo respeta el área de trabajo para dejar sitio a la barra de tareas.

## Dictado

Pulsa Intro con la línea vacía, di la orden y confirma la transcripción con `s`. Para dictar necesitas un micrófono y un motor de reconocimiento en español compatible con System.Speech en Windows PowerShell. Puedes escribir órdenes sin configurar el micrófono. El proyecto usa la biblioteca estándar de Python.

## Estado del proyecto

El prototipo mueve ventanas y muestra respuestas en la terminal. Las peticiones libres y las acciones encadenadas quedan para futuras versiones. Se verificó el análisis de órdenes y el cálculo geométrico en Linux. Queda pendiente validar el movimiento y el dictado en un equipo Windows.

Consulta la [guía de desarrollo](Guia.md) para resolver problemas o añadir comandos.
