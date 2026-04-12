# Integración Realidad Aumentada (RA) - Backend API

## Seguridad (Sesión)
Las llamadas RA en esta app usan sesión autenticada (cookie same-origin).
No se debe enviar `X-API-Key` desde el cliente web.

## Base URL (local)
- `http://127.0.0.1:5000`

---

## 1) Consultar material (para mostrar info en RA)

**GET**
`/api/ra/materials/<material_id>`

### Ejemplo (PowerShell)
```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/ra/materials/1" `
  -Method Get `
  -WebSession $session
