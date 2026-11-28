# Canales de actualización

El canal **Estable** es el predeterminado. Solo ofrece publicaciones estables con un JARVIS.exe verificable. El canal **Experimental**, que debe activarse voluntariamente, añade las prereleases de GitHub publicadas para pruebas. Se elige desde la bandeja y se conserva por usuario.

La opción **Canal estable** permite pedir un regreso explícito desde una candidata. Se comprueban la disponibilidad, el tamaño y la huella del ejecutable; el cambio de canal por sí solo no instala una versión. Pulsa **Actualizar y reiniciar** y revisa la confirmación. La sustitución espera al cierre de la instancia, conserva una copia local hasta verificar el nuevo arranque y restaura el original si falla. No modifica los perfiles biométricos ni la configuración del usuario.

El actualizador consulta release-policy.json en la rama experimental además del registro incluido en su propio ejecutable. Si no puede comprobar el registro remoto, puede seguir utilizándose JARVIS y reintentar más tarde. Las versiones bloqueadas no se ofrecen y la prohibición se comprueba de nuevo antes de descargar. [Registro de descargas retiradas](versiones-defectuosas.md)

rc.2 y las revisiones anteriores no tienen selector de canal. Para la primera transición, cierra JARVIS completamente en la bandeja y reemplaza su ejecutable en la ubicación actual por el activo de la prerelease. Después selecciona **Canal experimental**. Las siguientes candidatas podrán llegar desde el propio asistente.

Si autorizas volver a un binario anterior a rc.3, ese binario carece del selector de canal. Para entrar otra vez en el canal experimental desde allí necesitarás de nuevo un ejecutable que incluya el selector. Cambiar la preferencia a Estable sin instalar una versión antigua conserva el selector actual.
