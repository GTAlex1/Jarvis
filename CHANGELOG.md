# Cambios de JARVIS

## 0.6.4

- Verificación local del hablante para activaciones y turnos. Registro, renombrado, renovación y eliminación de perfiles con tres muestras. Firmas cifradas para la cuenta de Windows con DPAPI.
- Confirmación con un código local desde la bandeja para cerrar ventanas, bloquear Windows, capturar la pantalla, abrir herramientas administrativas y salir de JARVIS por voz.
- Normalización de órdenes en español y búsqueda fonética en las aplicaciones y ventanas detectadas. Las coincidencias aproximadas requieren una aclaración.
- Captura WASAPI compartida con búfer del dispositivo. Se conservan MME y DirectSound, y ASIO se usa con selección explícita. Filtrado local de ruido grave y diagnóstico de bloques perdidos.
- Los perfiles de voz son un requisito para la escucha permanente. La consola mantiene la entrada por teclado. La voz del programa se administra desde la bandeja.
- La verificación de voz tiene límites frente a grabaciones, imitaciones y voces sintéticas. La convivencia con Discord y WhatsApp se comprueba con micrófono y llamada reales.

## 0.6.3

- Conversación local con contexto temporal, respuestas habladas por partes, aclaraciones e interrupción.
- Selección de interfaces disponibles y reintento de formatos dentro de WASAPI.

Consulta el [historial de versiones anteriores](https://github.com/GTAlex1/Jarvis/releases).
