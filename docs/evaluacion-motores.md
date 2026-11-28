# Motores locales para órdenes y juegos

| Motor | Aceleración y recursos | Qué aporta y qué falta comprobar |
| --- | --- | --- |
| PocketSphinx + Vosk | CPU, sin VRAM; escucha por bloques. | Sigue a cargo de la activación y transcripción. El modelo acústico tiene un idioma principal. La segunda lectura contextual solo examina candidatos locales y no cambia el verbo. |
| Whisper (OpenAI) | CPU o GPU según la instalación de PyTorch. Tiny y Base requieren aproximadamente 1 GB de VRAM según el proyecto; Small unos 2 GB. | Tiene modelos multilingües y detección de idioma. Las cifras de velocidad oficiales se midieron en una NVIDIA A100. No permiten inferir la latencia de órdenes cortas ni en una Radeon. |
| faster-whisper | CPU int8 con CTranslate2; su ruta de GPU documentada requiere CUDA. | Útil como referencia local en CPU en el equipo AMD. Se midió también Tiny multilingüe int8 en CPU con el corpus de esta candidata. |
| whisper.cpp | CPU y cuantización; backend Vulkan y alternativa CPU. | Es la opción que se quiere medir en la RX 7700 XT para segunda lectura puntual. El entorno de CI no expone esa GPU, ni una sesión de juego. |

Las implementaciones son locales una vez obtenidos sus pesos. No hay cambio de motor de producción o de umbrales biométricos. Un modelo que gane en dictado largo puede perder en activaciones, nombres propios cortos o latencia de consola. Antes de seleccionar un segundo motor hay que medir nombres extranjeros, falsas activaciones, latencia y rendimiento coexistiendo con un juego real.

Ejecuta el corpus sintético con python benchmark_voice.py. Para comparar un modelo externo, usa --whisper-path con pesos CTranslate2 locales, o --whisper-cpp y --whisper-ggml con un binario y un modelo locales. La variante de CLI incluye el coste de arrancar el proceso y cargar el modelo para cada clip. Usa --vulkan solo con un binario compilado con soporte Vulkan. Linux puede medir tiempo de CPU hijo, pero la VRAM, consumo de GPU y penalización en FPS deben medirse en el equipo real. No se usan clips de micrófono ni datos biométricos en estas pruebas.

Fuentes: [Vosk](https://alphacephei.com/vosk/models), [Whisper](https://github.com/openai/whisper), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [whisper.cpp](https://github.com/ggml-org/whisper.cpp).

## Medición de rc.3

Diez órdenes sintéticas y controles del corpus activo, en Linux sobre Intel Xeon Platinum 8370C. Vosk usa el arco completo de activación y orden. faster-whisper usó Tiny multilingüe int8 con el modelo cargado entre clips. whisper.cpp v1.7.6 usó Tiny multilingüe Q5_1 (32,2 MB) en CPU, dos hilos y un proceso nuevo por clip. El total de CPU suma el tiempo de los hilos. El pico de RAM representa el mayor proceso medido, no la suma de consumos.

| Configuración | Casos correctos | Mediana por clip | CPU total | Pico de RAM |
| --- | ---: | ---: | ---: | ---: |
| Vosk + PocketSphinx | 8/10 | 818 ms | 7,8 s | 185 MiB |
| faster-whisper Tiny int8 en CPU | 3/10 | 1.496 ms | 30,1 s | 276 MiB |
| whisper.cpp Tiny Q5_1 en CPU | 3/10 | 1.861 ms | 38,2 s | 190 MiB |

faster-whisper y whisper.cpp acertaron los tres controles sin orden, pero ningún comando válido del corpus con palabra de activación. El resultado no estima el rendimiento de un modelo mayor ni una segunda lectura de audio que ya excluya la palabra de activación. En la prueba de esta candidata no se usó VRAM para estas tres configuraciones. Queda medir nombres extranjeros, consumo de GPU y VRAM y latencia en la RX 7700 XT mientras se juega. La [guía](../Guia.md#evaluación-de-motores-y-rendimiento) conserva la comparación histórica de faster-whisper.

Para registrar la coexistencia en la Radeon, ejecuta el mismo corpus en CPU y con Vulkan, con idénticos pesos y número de hilos, primero en escritorio y después con el mismo juego y escena. Anota mediana y percentil 95 por orden, CPU, memoria dedicada y compartida y cambios de FPS. Para evaluar el habla real harán falta frases consentidas en ambos idiomas y los nombres de aplicaciones que se usan habitualmente.
