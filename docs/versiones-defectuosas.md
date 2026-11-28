# Registro de versiones y descargas

El registro central de versiones está en [release-policy.json](../assets/release-policy.json). Conserva fechas, canales, estado, incidencias y sustitución. «Obsoleta» significa que existe una nueva revisión. La mera presencia de limitaciones no justifica retirar una descarga.

| Versión | Estado | Motivo y alternativa |
| --- | --- | --- |
| 0.6.5-rc.1 | Retirada el 28 de noviembre de 2026 | Una referencia a game_roots sin inicializar detenía el catálogo. Se retiraron los artefactos de Actions 15263069144 y 15263074998 tras publicar rc.3. |
| 0.6.5-rc.2 | Obsoleta | Conserva el historial y el artefacto de CI. Sus limitaciones de voz, confirmación y rutas no se clasifican como retirada. |
| 0.6.5-rc.3 | Experimental disponible | El ejecutable pasó empaquetado, pruebas automatizadas y actualización con rollback. Queda pendiente la validación física. [Prerelease](https://github.com/GTAlex1/Jarvis/releases/tag/v0.6.5-rc.3) |

El flujo de publicación verifica el ejecutable con SHA-256 y confirma que la candidata está disponible antes de retirar descargas de rc.1. Revalida cada identificador de artefacto y su commit de origen. rc.1 no tuvo una release ni un activo que el actualizador fuese a descargar. Las pruebas empaquetadas usan activos de 0.4.1, 0.6.4, 0.6.4.1 y 0.6.4.2. El rollback conserva su copia del ejecutable de la instalación local. Se preservan por tanto esos activos, los commits, la wiki, el historial de CI y el changelog.

[Canales, preferencias y recuperación](actualizaciones.md)
