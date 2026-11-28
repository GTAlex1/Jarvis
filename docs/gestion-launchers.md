# Cierre de videojuegos y launchers

«Cierra [juego]» envía WM_CLOSE a su ventana y respeta los avisos propios del juego. El seguimiento comprueba el proceso del juego y espera si vuelve a aparecer una ventana del cliente. «Cierra [juego] y su launcher» solicita también la comprobación del cliente. «Cierra [juego], pero deja [cliente] abierto» omite esa segunda acción. «Cierra los launchers que no estoy utilizando» explica la necesidad de verificar cada asociación antes de cerrar.

En la bandeja, **Cierre de videojuegos y launchers…** permite activar la solicitud global y mantener abiertos proveedores o juegos concretos. Está apagada inicialmente. Introduce claves como epic, hoyoplay, steam, riot, ea, battlenet, ubisoft, gog o xbox, o nombres de juegos separados por comas. La solicitud explícita respeta las excepciones y los permisos de cierre.

El supervisor comprueba el proveedor, la ruta del cliente registrado, el proceso, la hora de inicio y la ventana. Conserva el cliente si detecta otro juego vinculado, un arranque pendiente, varias sesiones o una tarea activa. También exige evidencia de que no hay descargas, actualizaciones o instalaciones. **Epic y HoYoPlay aún no tienen un adaptador que confirme que su cliente está libre.** JARVIS comprueba el cierre del juego y explica por qué conserva el launcher. El cierre en estado libre se cubre mediante proveedores simulados. Se usa el cierre normal de Windows.

Si el juego está detectado por los metadatos del instalador y carece de acceso directo específico, JARVIS puede abrir la entrada registrada de HoYoPlay. Selecciona el título y pulsa Jugar en el cliente. JARVIS solo confirma el arranque si comprueba la identidad del juego. [HoYoPlay FAQ](https://www.hoyolab.com/article/29394693)
