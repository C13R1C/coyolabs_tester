# Auditoría técnica de estabilidad demo (2026-04-09)

## Hallazgos críticos

1. **Adeudos invisibles en home de usuario**
   - `home_controller` consulta `Debt.status == "OPEN"`, pero el modelo y servicios operan con `PENDING`/`PAID`.
   - Riesgo: usuarios con adeudo activo no lo ven en home y demo muestra estado financiero incorrecto.

2. **Publicación SSE sin aislamiento en caminos críticos de negocio**
   - En aprobación de reservaciones y creación de solicitudes 3D se invoca `publish_notification_created(...)` sin `try/except`.
   - Si falla la publicación (pool, sesión, broker), la petición puede terminar en 500 aunque la operación principal sí se haya ejecutado.

3. **Broker SSE no distribuido por proceso**
   - El propio servicio indica que el broker es process-local.
   - En despliegue con múltiples workers, clientes conectados a otro worker no reciben eventos.

## Hallazgos medios

4. **Inconsistencia de codificación de laboratorios (E1/E001)**
   - Catálogos de cuartos usan `E1..E6` mientras otros contextos institucionales suelen manejar formatos con ceros (`E001`).
   - Riesgo de filtros vacíos, confusión en agenda y discrepancias en reporte durante demo.

5. **Reserva permite fecha pasada**
   - Se valida formato, ventana horaria y solapamiento, pero no hay rechazo explícito para fechas anteriores al día actual.
   - Riesgo: datos inválidos de operación real y ruido en paneles administrativos.

6. **Conciliación de deudas por coincidencia débil**
   - `create_debt_for_ticket` reutiliza adeudo `PENDING` por usuario/material si `ticket_id` coincide o es `NULL`.
   - Riesgo: fusionar adeudos no relacionados (históricos/manuales) al cerrar ticket.

7. **Cuenta creada aunque falle correo de verificación**
   - En registro se hace `commit` antes de enviar correo.
   - Si falla email, queda usuario no verificado persistido y el flujo depende de recuperación manual.

## Hallazgos menores

8. **Estado por strings hardcodeados en home**
   - Se usa `"APPROVED"/"PENDING"` en lugar de constantes centralizadas.
   - Riesgo de deriva si cambian alias/normalización de estados.

9. **Metadatos operativos embebidos en `notes` por marcadores string**
   - En inventario diario se infieren estados por tokens tipo `[CERRADO_CON_ADEUDO]`.
   - Riesgo: fragilidad ante edición manual del texto o cambios de copy.

10. **Ruta de uploads con normalización sin verificación de raíz permitida**
   - Se usa `normpath` y se sirven candidatos existentes, pero no hay `commonpath` para forzar contención dentro de carpetas permitidas.
   - Riesgo de exposición accidental de archivos fuera de scope por rutas relativas maliciosas.

## Recomendación de estabilización (sin refactor grande)

- Priorizar parches de baja invasión:
  1. Cambiar `OPEN` por `DebtStatus.PENDING` en home.
  2. Encapsular `publish_notification_created` en `try/except` en endpoints críticos.
  3. Añadir guard clause de fecha no pasada en reserva.
  4. Restringir reuse de deuda por `ticket_id` y/o prefijo de razón controlado.
  5. Normalizar catálogo de rooms (mapa de equivalencias `E001 <-> E1`).
  6. Proteger ruta `/uploads` con validación de raíz de directorio.
