# Cambios de JARVIS

## 0.6.4.2 · Validación interna

- Separación del detector de activación y de la transcripción. Una segunda comprobación léxica valida variantes acústicas del inicio de una frase. El búfer guarda el inicio de la orden para transcripción y verificación.
- Normalización de verbos y clíticos, corrección de nombres habituales y selección directa de destinos exactos deduplicados. Las órdenes sensibles con confianza insuficiente se rechazan. Adaptación de voz opcional y local desde la bandeja.
- La biometría usa el intervalo de las palabras reconocidas. La activación sola carece de autorización y la evidencia combinada solo se admite para ayuda. Los eventos distinguen audio, activación, texto, hablante, permiso y resultado.
- El actualizador compara versiones numéricas y preliminares, comprueba la versión arrancada y restaura la anterior si el binario nuevo falla. Detección compatible desde 0.6.4.1.
- Validación física de la revisión pendiente. En 0.6.4.1 se informaron 14 comprobaciones correctas, cinco parciales, dos fallidas y una pendiente. En ese equipo dejó de reproducirse la distorsión durante llamadas. [Pruebas físicas](Guia.md#comprobaciones-físicas-de-0642)

## 0.6.4.1

- **BUG-064-001**. Se elimina el veto biométrico de la palabra de activación aislada y se comparte la extracción con el registro. Las órdenes se verifican con su propio audio. Una orden breve puede incorporar la activación de la misma intervención si es continua. Se distinguen insuficiencia, falta de coincidencia y problemas de audio o perfil.
- Los perfiles muestran calidad por muestra, permiten repetir una grabación, exigen una comprobación independiente antes del alta y permiten comprobar perfiles guardados. Diagnóstico exportable sin audio ni firmas.
- Seguridad y permisos desde panel y bandeja. Libertad, Equilibrado, Estricto y Personalizado, con biometría independiente. Confirmaciones específicas, caducables y de un solo uso.
- Apagado y reinicio con cuenta atrás cancelable. Captura de pantalla completa mediante Windows. Se respetan los avisos de trabajo sin guardar.
- Admite cuatro componentes en nuevas actualizaciones. Para adoptar 0.6.4.1 desde una versión anterior, cierra JARVIS y reemplaza el ejecutable. Se conservan perfiles y preferencias.
- La verificación con la voz del propietario, el rechazo de terceros reales y las llamadas de Discord o WhatsApp siguen pendientes de validación física.

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
