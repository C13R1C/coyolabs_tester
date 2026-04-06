# Revisión de robustez — SUBFASE 0 y SUBFASE 1

## 1) Compatibilidad con legacy

### Estado
- `users.academic_level_id`, `subjects.academic_level_id` y `reservations.subject_id` se agregaron como columnas `NULLABLE`, por lo que no obligan backfill inmediato y no rompen registros existentes.
- Se conservaron campos legacy (`users.academic_level`, `subjects.level`, `reservations.subject` texto), manteniendo compatibilidad con rutas/formularios actuales durante transición.

### Veredicto
- **Compatible en esta etapa**, con transición gradual posible.

## 2) Bloqueo backend de edición posterior en `complete_profile`

### Estado
- `complete_profile` impide reingreso cuando `profile_completed` ya es `True`.
- En esta subfase no existe ruta de autoedición de nombre/matrícula/carrera/nivel para STUDENT/TEACHER, por lo que los campos quedan efectivamente bloqueados para el propio usuario tras confirmación.

### Veredicto
- **Sí bloquea en backend en el flujo actual**.

### Nota
- El panel administrativo sí puede editar esos campos por diseño (flujo ADMIN/SUPERADMIN), lo cual no contradice la regla para autoedición de usuario final.

## 3) Duplicados de solicitudes `PENDING` para STUDENT

### Estado
- El endpoint de solicitud de teléfono consulta si ya existe una solicitud `PENDING` de tipo `PHONE_CHANGE` para el usuario y bloquea la creación de otra.

### Veredicto
- **Sí evita duplicados PENDING a nivel de aplicación**.

### Riesgo residual recomendado
- Agregar índice único parcial en DB para reforzar esta regla ante concurrencia.

## 4) Validación de teléfono en edición directa de TEACHER

### Estado
- Solo se valida que no venga vacío.
- No hay validación de formato, longitud ni normalización (trim + dígitos/caracteres permitidos).

### Veredicto
- **Insuficiente para robustez fuerte**.

### Recomendación menor antes de SUBFASE 2
- Validar longitud mínima/máxima (ej. 8-20).
- Normalizar espacios/guiones.
- Restringir caracteres a patrón telefónico permitido.

## 5) Restricciones mínimas de `profile_change_requests` e integración admin

### Estado
- DB tiene checks de `status` y `request_type`.
- Tiene FKs a usuario solicitante y revisor.
- Hay pantalla administrativa para listar/aprobar/rechazar.
- Al aprobar `PHONE_CHANGE`, se actualiza `users.phone` y se registra auditoría en bitácora.

### Veredicto
- **Correcto y suficientemente integrado para esta subfase**.

## 6) Rutas nuevas expuestas y roles

### Perfil
- `POST /profile/phone-change/request`
  - `@login_required`
  - Uso efectivo: STUDENT (TEACHER recibe bloqueo por regla de negocio).
- `POST /profile/phone/update`
  - `@login_required`
  - Uso efectivo: TEACHER únicamente.

### Administración
- `GET /users/admin/profile-change-requests`
  - `@min_role_required("ADMIN")`
  - Uso: ADMIN y SUPERADMIN.
- `POST /users/admin/profile-change-requests/<request_id>/approve`
  - `@min_role_required("ADMIN")`
  - Uso: ADMIN y SUPERADMIN.
- `POST /users/admin/profile-change-requests/<request_id>/reject`
  - `@min_role_required("ADMIN")`
  - Uso: ADMIN y SUPERADMIN.

## Ajustes menores recomendados antes de continuar

1. Validación fuerte de teléfono (formato/longitud/normalización) en:
   - edición directa de TEACHER;
   - creación de solicitud STUDENT.
2. Índice único parcial para `PHONE_CHANGE` en estado `PENDING` por usuario (si la BD lo soporta).
3. Considerar ocultar o deprecar endpoint legacy `POST /profile/request-update` para evitar duplicidad de flujos.
