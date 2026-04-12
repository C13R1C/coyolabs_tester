# Auditoría técnica de cierre demo — 2026-04-12

Hallazgos priorizados para estabilización de demo en CoyoLabs.

## Críticos
- Exposición arbitraria de archivos por `/uploads/<path>` sin control de autenticación ni validación de path traversal.

## Altos
- XSS DOM en vistas administrativas (renderizado con `innerHTML` de datos de usuario sin escape).
- IDOR en Lost&Found: usuarios no admin pueden abrir casos `RETURNED` por URL directa.
- Datos sensibles/versionables dentro del repositorio (`sqldump` con datos reales y uploads persistidos).

## Medios
- Inconsistencia de autenticación API RA: sesión autenticada omite API key.
- Desalineación modelo/migración (`materials.image_url`, longitud `notifications.event_code`).
- SSE process-local (riesgo en despliegue multi-worker).
- Plantillas aparentemente huérfanas.

## Bajos
- `run.py` arranca en `debug=True`.
- Duplicación alta de lógica JS/HTML entre cliente RA normal y fullscreen.
