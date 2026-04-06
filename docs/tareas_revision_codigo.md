# Tareas propuestas tras revisión del código base

## 1) Corregir error tipográfico en la interfaz de autenticación
**Tipo:** Error tipográfico

**Hallazgo:** En el formulario de registro aparece el texto `Volver a login`, mezclando inglés y español en una etiqueta visible para el usuario.

**Tarea propuesta:** Cambiar el texto del botón a una opción en español consistente, por ejemplo `Volver a iniciar sesión`.

**Criterios de aceptación:**
- El botón de cambio de modo en registro ya no muestra el anglicismo `login`.
- El texto del flujo de autenticación usa terminología consistente en español.

**Referencia:** `app/templates/auth/auth.html` (línea 146).

---

## 2) Corregir falla de validación de contraseña en backend
**Tipo:** Falla funcional

**Hallazgo:** El frontend solicita `confirm_password`, pero el endpoint `/auth/register` solo toma `password` y no valida coincidencia. Esto permite crear cuentas aunque el usuario haya escrito una confirmación distinta.

**Tarea propuesta:** En `register()`, leer `confirm_password` y rechazar el registro cuando no coincida con `password`.

**Criterios de aceptación:**
- Si `password != confirm_password`, el backend responde con `flash` de error y no crea usuario.
- Se mantiene la validación actual de longitud mínima.
- Se agrega cobertura de prueba para este caso (ver tarea 4).

**Referencias:** `app/templates/auth/auth.html` (líneas 126-128), `app/controllers/auth_controller.py` (líneas 73-99).

---

## 3) Corregir discrepancia en documentación/comentarios de la API RA
**Tipo:** Discrepancia documentación/comentarios

**Hallazgo:** `README_RA.md` está incompleto (bloque PowerShell sin cierre y sin ejemplos del resto de endpoints), lo que no refleja completamente el comportamiento implementado en `api_controller.py`.

**Tarea propuesta:** Completar `README_RA.md` con:
- cierre correcto del bloque de código,
- ejemplo de `POST /api/ra/events` con `user_email`,
- respuestas esperadas (201, 400, 403, 404),
- breve tabla de campos mínimos.

**Criterios de aceptación:**
- El markdown renderiza correctamente sin bloques abiertos.
- Se documentan los endpoints RA implementados.
- Los ejemplos incluyen los campos realmente requeridos por el backend.

**Referencias:** `README_RA.md` (líneas 21-28), `app/controllers/api_controller.py` (líneas 73-122).

---

## 4) Mejorar pruebas del flujo de QR y parsing de ID
**Tipo:** Mejora de pruebas

**Hallazgo:** Existe lógica de parsing flexible (`extractMaterialId`) para QR como `material:2` o `id=2`, pero `onScanSuccess` usa `Number(decodedText)` directamente y deja inactiva esa cobertura real.

**Tarea propuesta:**
- Ajustar `onScanSuccess` para usar `extractMaterialId(decodedText)`.
- Crear pruebas unitarias para `extractMaterialId` y pruebas de integración de `onScanSuccess` con casos válidos/no válidos.

**Criterios de aceptación:**
- Los formatos `2`, `material:2`, `material_id:2` e `...?id=2` se aceptan en el flujo de escaneo.
- Se mantiene rechazo para QR sin ID numérico.
- Las pruebas cubren anti-regresión del parser y la ruta de error.

**Referencias:** `app/static/js/app.js` (líneas 73-92, 136-143).
