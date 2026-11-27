# Guía de JARVIS

## Ejecutable de Windows

GitHub Actions compila `jarvis_gui.py` con PyInstaller y comprueba que `JARVIS.exe` abre la ventana. El resultado se adjunta como `JARVIS-Windows-x64` a la ejecución. Puedes abrir la [última compilación](https://github.com/GTAlex1/Jarvis/actions/workflows/windows.yml) desde el repositorio.

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

1. Añade la interpretación de la frase en `execute()`, que utilizan la consola y la interfaz gráfica.
2. Separa la interpretación del texto de la acción de Windows, como hacen `parse_move()` y `Desktop.move()`.
3. Incluye un ejemplo en `HELP` y documenta el comando en el README.
4. Comprueba la frase válida, una variante y una entrada inválida. Para cambios en las ventanas, comprueba también una ventana maximizada y un monitor secundario.

Puedes comprobar que el código compila con `python -m py_compile jarvis.py jarvis_gui.py`.
