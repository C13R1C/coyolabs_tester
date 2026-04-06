# Arquitectura ajustada: perfiles académicos, carga docente y reservaciones

## 1) Arquitectura ajustada final

### Decisiones cerradas
- Se conserva el modelo formal de carga docente con **`teacher_id + subject_id + group_code`** (sin tabla global nueva de grupos).
- `group_code` se normaliza en backend a MAYÚSCULAS.
- Se evita introducir estructuras no pedidas:
  - no `requested_by_role` en `reservations`;
  - no `locked_identity_fields` en `users`;
  - no `phone_change_requested` en `users`.
- Cambios de teléfono:
  - STUDENT: solo vía `profile_change_requests`;
  - TEACHER: edición directa permitida.
- Catalogación oficial:
  - ADMIN/SUPERADMIN gestionan carreras, niveles y materias.
  - STUDENT/TEACHER solo consumen catálogo.

### Modelo funcional por rol
- STUDENT:
  - completa perfil con datos obligatorios + checkbox de confirmación;
  - después de confirmar, no edita directamente nombre, matrícula, carrera, nivel ni teléfono;
  - reserva simple: materia filtrada por carrera + nivel, sin grupo obligatorio.
- TEACHER:
  - flujo propio de perfil con mismos obligatorios (nivel si aplica);
  - no edita nombre/matrícula;
  - sí edita teléfono;
  - carga académica propia por (`teacher_id`, `subject_id`, `group_code`);
  - reservación por combobox de materia/grupo según su carga.
- ADMIN/SUPERADMIN:
  - administración de catálogo;
  - control operativo;
  - desactivación de usuarios;
  - acciones críticas de eliminación bajo aprobación de SUPERADMIN.

## 2) Qué cambios exactos van en SUBFASE 0

### Objetivo
Dejar esquema mínimo y seguro, sin romper compatibilidad y sin implementar aún la lógica completa de reservaciones inteligentes.

### Tablas y columnas mínimas necesarias

#### A) `academic_levels` (nueva)
Necesaria porque hoy el nivel vive como texto y debe gestionarse como catálogo.

```sql
CREATE TABLE academic_levels (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_academic_levels_code UNIQUE (code),
    CONSTRAINT uq_academic_levels_name UNIQUE (name)
);

CREATE INDEX ix_academic_levels_is_active ON academic_levels (is_active);
```

#### B) `users` (ajustes mínimos)
- agregar FK formal a nivel;
- agregar confirmación explícita de datos;
- no agregar bloqueos extra no pedidos.

```sql
ALTER TABLE users
    ADD COLUMN academic_level_id INTEGER,
    ADD COLUMN profile_data_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN profile_confirmed_at TIMESTAMP;

ALTER TABLE users
    ADD CONSTRAINT fk_users_academic_level_id
    FOREIGN KEY (academic_level_id) REFERENCES academic_levels(id);

CREATE INDEX ix_users_academic_level_id ON users (academic_level_id);
CREATE INDEX ix_users_career_level ON users (career_id, academic_level_id);
```

#### C) `subjects` (ajuste mínimo)
- agregar FK a nivel académico para dejar de depender de texto libre.

```sql
ALTER TABLE subjects
    ADD COLUMN academic_level_id INTEGER;

ALTER TABLE subjects
    ADD CONSTRAINT fk_subjects_academic_level_id
    FOREIGN KEY (academic_level_id) REFERENCES academic_levels(id);

CREATE INDEX ix_subjects_academic_level_id ON subjects (academic_level_id);
```

#### D) `profile_change_requests` (nueva)
Necesaria para que STUDENT solicite cambio de teléfono (y otros cambios administrados).

```sql
CREATE TABLE profile_change_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    request_type VARCHAR(30) NOT NULL,
    requested_phone VARCHAR(30),
    reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    reviewed_by INTEGER,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT fk_profile_change_requests_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_profile_change_requests_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(id),
    CONSTRAINT ck_profile_change_requests_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    CONSTRAINT ck_profile_change_requests_type CHECK (request_type IN ('PHONE_CHANGE', 'PROFILE_CHANGE'))
);

CREATE INDEX ix_profile_change_requests_user_id ON profile_change_requests (user_id);
CREATE INDEX ix_profile_change_requests_status ON profile_change_requests (status);
```

#### E) `reservations` (ajuste mínimo compatible)
Solo FK de materia por ahora para empezar filtrado formal; sin `requested_by_role`.

```sql
ALTER TABLE reservations
    ADD COLUMN subject_id INTEGER;

ALTER TABLE reservations
    ADD CONSTRAINT fk_reservations_subject_id
    FOREIGN KEY (subject_id) REFERENCES subjects(id);

CREATE INDEX ix_reservations_subject_id ON reservations (subject_id);
CREATE INDEX ix_reservations_date_room_status ON reservations (date, room, status);
```

### Compatibilidad y backfill mínimo
- `users.academic_level` y `subjects.level` se conservan temporalmente para histórico/migración.
- backfill recomendado:
  1) poblar `academic_levels` con TSU/ING;
  2) mapear `users.academic_level -> users.academic_level_id`;
  3) mapear `subjects.level -> subjects.academic_level_id`.

## 3) Qué archivos tocaría en SUBFASE 1

### Backend
- `app/controllers/profile_controller.py`
  - `complete_profile`: validaciones por rol + checkbox obligatorio + guardado de `profile_data_confirmed/profile_confirmed_at` + guardado de `academic_level_id`.
  - reglas de edición:
    - STUDENT: impedir edición directa de teléfono en rutas de perfil;
    - TEACHER: permitir edición directa de teléfono.
  - nombre/matrícula no editables una vez confirmado perfil.
- `app/controllers/users_controller.py`
  - endpoints de revisión de `profile_change_requests` por ADMIN/SUPERADMIN.

### Modelos
- `app/models/user.py`
  - mapear columnas nuevas (`academic_level_id`, `profile_data_confirmed`, `profile_confirmed_at`).
- `app/models/subject.py`
  - mapear `academic_level_id`.
- `app/models/profile_change_request.py` (nuevo)
  - modelo para solicitudes de cambio.
- `app/models/__init__.py`
  - exportar modelo nuevo.

### Plantillas
- `app/templates/profile/complete.html`
  - checkbox obligatorio de confirmación de datos.
  - select de nivel desde catálogo, no hardcode.
- `app/templates/profile/my_profile.html`
  - mostrar sección de “solicitar cambio de teléfono” para STUDENT.
  - mostrar edición directa de teléfono para TEACHER.

### Migraciones
- nueva migración Alembic para SUBFASE 0.

## 4) Qué tablas/modelos necesito realmente

### Necesarios ahora (SUBFASE 0-1)
- `users` (ajustes mínimos).
- `subjects` (FK de nivel).
- `reservations` (FK de materia para transición a reservación inteligente).
- `academic_levels` (nuevo catálogo).
- `profile_change_requests` (solicitudes de cambio para STUDENT).
- `teacher_academic_loads` (se mantiene estructura actual formal con `teacher_id/subject_id/group_code`).

### No necesarios ahora
- tabla global separada de grupos.
- nuevas columnas auxiliares no pedidas (`requested_by_role`, `locked_identity_fields`, `phone_change_requested`).

## 5) Qué NO voy a tocar todavía

- SUBFASE 2 completa de carga académica (UI/flujo avanzado de agregar/quitar materia+grupo), salvo preparar compatibilidad.
- SUBFASE 3 de reservaciones inteligentes completa (combobox final por rol y validaciones finales de persistencia).
- eliminación definitiva de columnas legacy (`users.academic_level`, `subjects.level`, `reservations.subject` texto) hasta terminar transición y backfill validado.
- rediseño de agenda avanzada de laboratorios fuera del alcance actual.

## 6) Cómo probar SUBFASE 0 y SUBFASE 1

### Pruebas de SUBFASE 0 (esquema)
1. Ejecutar migración en entorno local.
2. Verificar estructura creada/alterada:
   - existencia de `academic_levels` y `profile_change_requests`;
   - nuevas columnas en `users`, `subjects`, `reservations`;
   - FKs e índices.
3. Verificar backfill mínimo:
   - usuarios con `academic_level` legacy mapeados a `academic_level_id`;
   - materias con `level` legacy mapeadas a `academic_level_id`.
4. Validar que flujos existentes no se rompen (login, perfil, reserva tradicional).

Comandos sugeridos:
- `flask db upgrade`
- `flask db current`
- consultas SQL manuales de conteo nulos y FKs

### Pruebas de SUBFASE 1 (perfil)

#### STUDENT
- completar perfil exige campos obligatorios + checkbox.
- al confirmar, no puede editar nombre/matrícula/carrera/nivel/teléfono.
- puede crear solicitud de cambio de teléfono y queda en `PENDING`.

#### TEACHER
- completar perfil con obligatorios (nivel si aplica política).
- no puede editar nombre/matrícula tras confirmar.
- sí puede editar teléfono directamente.

#### ADMIN/SUPERADMIN
- listar solicitudes `profile_change_requests`.
- aprobar/rechazar solicitud de cambio de teléfono.
- al aprobar, se actualiza `users.phone` y se registra `reviewed_by/reviewed_at`.

#### Regresión mínima
- registro/verificación/login siguen operando;
- `profile_completed` mantiene su comportamiento de puerta de entrada.

---

## Contexto crítico faltante del repo (explícito)
- No se identifica aún un módulo dedicado de catálogo académico (CRUD de carreras/niveles/materias) ya implementado en controladores/vistas.
- No se observa todavía un modelo existente para solicitudes de cambio de perfil persistentes; hoy se usa notificación simple.
- Antes de SUBFASE 2 conviene confirmar UX final para distinguir “agregar materia” vs “agregar grupo” sobre la estructura actual (`teacher_academic_loads`).
