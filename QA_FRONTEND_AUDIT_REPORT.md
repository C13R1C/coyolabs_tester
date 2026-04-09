# Auditoría frontend de formularios (HTML/CSS)

Fecha: 2026-04-09
Alcance: revisión recursiva de `app/templates/**/*.html` y estilos en `app/static/css/*.css` + estilos embebidos en plantillas.

## Hallazgos

- 📁 **Archivo:** `app/templates/reservations/request.html`
- 📍 **Línea aproximada:** 369
- 🐛 **Problema detectado:** Campo `readonly` dentro de `.search-box` sin estilo visual diferenciado (solo lectura), por lo que puede verse como input editable o “plano” según el navegador.
- 🔧 **Código actual:**
  ```html
  <div class="search-box">
    <i class="ph ph-warning-circle search-icon"></i>
    <input type="text" value="No tienes grupos asignados" readonly>
  </div>
  ```
- 💡 **Solución sugerida:**
  ```css
  .search-box input[readonly],
  .form-control[readonly] {
    background: rgba(245,245,245,.9);
    color: var(--text-soft);
    cursor: default;
  }
  ```
  ```html
  <input type="text" value="No tienes grupos asignados" readonly aria-readonly="true">
  ```

---

- 📁 **Archivo:** `app/templates/reservations/request.html`
- 📍 **Línea aproximada:** 384-388
- 🐛 **Problema detectado:** Input de “Solicitante” prellenado (`readonly`) sin manejo de desbordamiento. Si el nombre/correo es largo, puede romper alineación visual en `flex`.
- 🔧 **Código actual:**
  ```html
  <input
    type="text"
    value="{{ (current_user.full_name or '')|trim or current_user.email }}"
    readonly
  >
  ```
- 💡 **Solución sugerida:**
  ```css
  .search-box input {
    min-width: 0;
  }

  .search-box input[readonly] {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  ```

---

- 📁 **Archivo:** `app/templates/reservations/request.html`
- 📍 **Línea aproximada:** 408
- 🐛 **Problema detectado:** Segundo campo informativo `readonly` (materias no asignadas) con el mismo patrón sin estilo específico de solo lectura; inconsistencia visual respecto a `.form-readonly-visual` definida globalmente.
- 🔧 **Código actual:**
  ```html
  <div class="search-box">
    <i class="ph ph-warning-circle search-icon"></i>
    <input type="text" value="No tienes materias asignadas" readonly>
  </div>
  ```
- 💡 **Solución sugerida:**
  ```html
  <div class="form-readonly-visual" role="status" aria-live="polite">
    <i class="ph ph-warning-circle"></i>
    <span>No tienes materias asignadas</span>
  </div>
  ```

---

- 📁 **Archivo:** `app/templates/prints3d/admin_detail.html`
- 📍 **Línea aproximada:** 122
- 🐛 **Problema detectado:** Input `readonly` con clase `.form-control` pero sin regla CSS dedicada para `readonly`; visualmente puede parecer campo editable y afectar claridad de estado.
- 🔧 **Código actual:**
  ```html
  <input class="form-control" type="text" value="{{ ('$' ~ ('%.2f'|format(job.total_estimated))) if job.total_estimated is not none else 'Se calcula automáticamente' }}" readonly>
  ```
- 💡 **Solución sugerida:**
  ```css
  .form-control[readonly] {
    background: rgba(245,245,245,.92);
    border-style: dashed;
    color: var(--text-soft);
  }
  ```
