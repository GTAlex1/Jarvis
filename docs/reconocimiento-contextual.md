# Reconocimiento contextual en JARVIS 0.6.5-rc.2

JARVIS mantiene Vosk para escuchar localmente. El modelo español viene en el ejecutable y conserva el reconocimiento de «Jarvis» y la verificación del hablante. Para usar inglés, abre la bandeja y elige **Voz en inglés…**. JARVIS descarga y comprueba el SHA-256 de Vosk Small en-US 0.15 (41.2 MB, licencia Apache 2.0). Después funciona sin conexión. Puedes volver a español en el mismo menú.

En una orden española, pronuncia el nombre comercial como lo dices habitualmente. El catálogo aporta los nombres y alias instalados. Si se reconoce el verbo y el destino no coincide exactamente, se comparan la forma escrita, la fonética y partes del nombre. Si hay audio del turno autorizado y el modelo conoce las palabras de los destinos más probables, un segundo reconocimiento local examina hasta tres hipótesis con un vocabulario acotado. Las hipótesis sugieren destinos; nunca sustituyen el verbo, cambian permisos ni omiten la confirmación. Esto también aplica a cierres.

Para confirmar un destino único, di «sí, adelante». Con varios destinos, di el nombre o el número. Si corriges un destino reconocido por voz, **Guardar última corrección…** aparece temporalmente en la bandeja. JARVIS guarda el alias tras tu confirmación. **Adaptación de voz** permite consultarlo, editarlo o eliminarlo en cualquier momento. Las frases de control siguen dependiendo del idioma seleccionado; los mensajes de interfaz y síntesis permanecen en español.

Cambiar de motor requiere elegir el idioma en la bandeja. El modelo español no contiene todos los nombres extranjeros, el inglés no es un modelo simultáneo para mezclas de idioma y los nombres que solo aparecen con escritura no latina pueden necesitar un alias local romanizado. La precisión para nombres japoneses, chinos o coreanos y para acentos reales queda pendiente de pruebas humanas. La segunda pasada solo usa nombres que existen en el léxico del modelo. Las transcripciones aproximadas simuladas y el audio sintético inglés verifican partes distintas del flujo.

Referencia de modelos y licencias: [Vosk Models](https://alphacephei.com/vosk/models).
