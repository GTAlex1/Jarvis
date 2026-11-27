# Guía de JARVIS

## Ejecutable de Windows

GitHub Actions compila `jarvis_gui.py` con PyInstaller y comprueba en Windows el arranque, el cierre a la bandeja, la instancia única y la sustitución y recuperación del ejecutable. El resultado se adjunta como `JARVIS-Windows-x64` a la ejecución. Puedes abrir la [última compilación](https://github.com/GTAlex1/Jarvis/actions/workflows/windows.yml) desde el repositorio.

## Ciclo de vida del asistente

- `assistant.py` ofrece la ejecución de comandos en serie. Un futuro origen de entrada puede enviar texto mediante `Assistant.submit()` y recibir el resultado sin depender del panel.
- `resident.py` coordina la sesión de escritorio, las preferencias y el actualizador. El panel de `jarvis_gui.py` se crea al abrirlo por primera vez.
- `windows_tray.py` registra el icono con Win32. Un mutex por sesión de Windows limita JARVIS a una instancia. Una segunda apertura manual solo pide mostrar el panel existente. La bandeja recupera el icono al reiniciarse Explorer.
- `preferences.py` guarda la preferencia del micrófono y administra el inicio de sesión en el registro del usuario. `--background` inicia JARVIS en la bandeja. Para probarlo desde el código usa `python jarvis_gui.py --background`.

Los comandos y la consulta de actualizaciones se completan en segundo plano. El panel recibe un aviso cuando hay resultados y suspende la animación al ocultarse. La comprobación de voz permanente queda pendiente. El dictado manual de consola conserva su confirmación antes de ejecutar una orden.

## Ventanas y pantallas

- Ejecuta `pantallas` para ver los identificadores disponibles. Las coordenadas pueden ser negativas cuando un monitor está a la izquierda o encima del principal.
- Prueba `VSCode izquierda`, `Chrome derecha monitor 2` o `Visual Studio Code pantalla completa`. Al maximizar, JARVIS usa el monitor indicado o el principal si lo omites.
- Ejecuta `ventanas` para ver los programas y sus títulos. Si hay dos ventanas de VS Code, usa una parte del título que identifique la ventana que quieres mover.
- Si la aplicación limita su tamaño mínimo, el asistente muestra las dimensiones solicitadas y las que consiguió aplicar.

## Micrófono

Comprueba que Windows PowerShell puede detectar un motor de reconocimiento en español:

```powershell
Add-Type -AssemblyName System.Speech
[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Select-Object Name, Culture
```

Si el listado carece de un motor en español o el dispositivo de entrada falla, puedes seguir dando órdenes escritas.

## Añadir un comando

1. Añade la frase al analizador de `commands.py` y conecta la acción en `execute()` de `jarvis.py`.
2. Separa la interpretación del texto de la acción de Windows, como hacen `parse_move()` y `Desktop.move()`.
3. Incluye un ejemplo en `HELP` y documenta el comando en el README.
4. Comprueba la frase válida, una variante y una entrada inválida. Para cambios en las ventanas, comprueba también una ventana maximizada y un monitor secundario.

Puedes ejecutar las pruebas con `python -m unittest -v test_commands test_resident`. En Windows, con Explorer activo, se prueba el icono y se verifica que el panel vuelva a abrirse desde la instancia existente. La prueba de actualización `python -m unittest -v test_update_windows` requiere el ejecutable `dist/JARVIS.exe`.

## Comandos desde la versión 0.4.0

La tabla completa de acciones está en [README.md](README.md#órdenes-de-windows). El analizador está en `commands.py`. Devuelve una acción y sus argumentos, que `execute()` aplica mediante `Desktop`.

`rectangle()` calcula las mitades, esquinas y posiciones usando coordenadas de Windows. Se prueban monitores con coordenadas negativas y dimensiones impares.

Ejecuta `python -m unittest -v test_commands` para comprobar las frases de ejemplo, la selección de ventanas y la geometría. En Windows, también se crea una ventana de prueba para comprobar posiciones, minimizar, maximizar, restaurar y recibir una solicitud de cierre que la ventana puede rechazar. Las pruebas no bloquean la sesión ni cambian el volumen.

El flujo de publicación ejecuta esas pruebas antes de generar el ejecutable y publicar la versión.
