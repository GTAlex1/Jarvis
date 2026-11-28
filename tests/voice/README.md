# Audio sintético de prueba

PCM mono de 16 bits, 16 kHz, comprimido con zlib y codificado en Base64. Las muestras son sintéticas y se usan para probar los motores sin un micrófono. Se concatenan con y sin pausa. Las pruebas también reproducen la orden sola y pasado el tiempo de espera.

- `wake-en.txt` contiene «Jarvis» de Flite, voz SLT, remuestreado a 16 kHz.
- `open-spotify.txt` contiene «abre Spotify» de eSpeak NG 1.52.0, voz `es`, velocidad 160, remuestreado a 16 kHz.
- `stop.txt` contiene «Jarvis, para» de eSpeak NG 1.52.0, voz `es`, velocidad 155, remuestreado a 16 kHz.

Las muestras `overhaul-*.txt` las generó eSpeak NG 1.51 con voces de España (`es`) y Latinoamérica (`es-419`), a velocidades entre 156 y 205 palabras por minuto, y se remuestrearon a 16 kHz. Incluyen ayuda, calculadora, reinicio, una negación, una frase sin activación y una que menciona «Jarvis» dentro de una conversación. La variante con pausa concatena la activación española, 500 ms de silencio y la orden sintética de Spotify del corpus original. Representan síntesis de voz y no son evidencia sobre hablantes reales, edades o acentos, incluido el andaluz.
