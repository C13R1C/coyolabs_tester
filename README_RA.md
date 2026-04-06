# Integración Realidad Aumentada (RA) - Backend API

## Seguridad (API Key)
Todas las llamadas RA requieren header:

- Header: `X-API-Key: <RA_API_KEY>`

La clave se define en `.env`:
- `RA_API_KEY=...`

## Base URL (local)
- `http://127.0.0.1:5000`

---

## 1) Consultar material (para mostrar info en RA)

**GET**
`/api/ra/materials/<material_id>`

### Ejemplo (PowerShell)
```powershell
$API_KEY = "TU_RA_API_KEY"

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/ra/materials/1" `
  -Method Get `
  -Headers @{ "X-API-Key" = $API_KEY }
