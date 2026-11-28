# Motores locales para órdenes y juegos

| Motor | Aceleración y recursos | Qué aporta y qué falta comprobar |
| --- | --- | --- |
| PocketSphinx + Vosk | CPU, sin VRAM; escucha por bloques. | Sigue a cargo de la activación y transcripción. El modelo acústico tiene un idioma principal. La segunda lectura contextual solo examina candidatos locales y no cambia el verbo. |
| Whisper (OpenAI) | CPU o GPU según la instalación de PyTorch. Tiny y Base requieren aproximadamente 1 GB de VRAM según el proyecto; Small unos 2 GB. | Tiene modelos multilingües y detección de idioma. Las cifras de velocidad oficiales se midieron en una NVIDIA A100. No permiten inferir la latencia de órdenes cortas ni en una Radeon. |
| faster-whisper | CPU int8 con CTranslate2; su ruta de GPU documentada requiere CUDA. | Útil como referencia local en CPU en el equipo AMD. Existe una medida anterior reproducible de Tiny int8 en la guía. |
| whisper.cpp | CPU y cuantización; backend Vulkan y alternativa CPU. | Es la opción que se quiere medir en la RX 7700 XT para segunda lectura puntual. El entorno de CI no expone esa GPU, ni una sesión de juego. |

Las implementaciones son locales una vez obtenidos sus pesos. No hay cambio de motor de producción o de umbrales biométricos. Un modelo que gane en dictado largo puede perder en activaciones, nombres propios cortos o latencia de consola. Antes de seleccionar un segundo motor hay que medir nombres extranjeros, falsas activaciones, latencia y rendimiento coexistiendo con un juego real.

Ejecuta el corpus sintético con python benchmark_voice.py. Para comparar un modelo externo, usa --whisper-path con pesos CTranslate2 locales, o --whisper-cpp y --whisper-ggml con un binario y un modelo locales. La variante de CLI incluye el coste de arrancar el proceso y cargar el modelo para cada clip. Usa --vulkan solo con un binario compilado con soporte Vulkan. Linux puede medir tiempo de CPU hijo, pero la VRAM, consumo de GPU y penalización en FPS deben medirse en el equipo real. No se usan clips de micrófono ni datos biométricos en estas pruebas.

Fuentes: [Vosk](https://alphacephei.com/vosk/models), [Whisper](https://github.com/openai/whisper), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [whisper.cpp](https://github.com/ggml-org/whisper.cpp).
