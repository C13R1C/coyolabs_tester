// =========================
// Utilidades UI
// =========================
function out(obj) {
  document.getElementById("out").textContent =
    typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function getBaseUrl() {
  return document.getElementById("baseUrl").value.trim().replace(/\/$/, "");
}

function headers() {
  const apiKey = document.getElementById("apiKey").value.trim();
  return { "X-API-Key": apiKey };
}

// =========================
// Modo Manual: GET / POST
// =========================
async function getMaterial() {
  const baseUrl = getBaseUrl();
  const id = document.getElementById("materialId").value;

  try {
    const res = await fetch(`${baseUrl}/api/ra/materials/${id}`, {
      method: "GET",
      headers: headers()
    });

    const data = await res.json().catch(() => null);
    out({ status: res.status, data });
  } catch (e) {
    out(String(e));
  }
}

async function postEvent() {
  const baseUrl = getBaseUrl();
  const id = Number(document.getElementById("materialId").value);
  const userEmail = document.getElementById("userEmail").value.trim().toLowerCase();

  const body = {
    material_id: id,
    event_type: "scan",
    user_email: userEmail,
    metadata: { device: "web-client", marker: `manual:${id}` }
  };

  try {
    const res = await fetch(`${baseUrl}/api/ra/events`, {
      method: "POST",
      headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    const data = await res.json().catch(() => null);
    out({ status: res.status, data });
  } catch (e) {
    out(String(e));
  }
}

// Exponer funciones para onclick del HTML
window.getMaterial = getMaterial;
window.postEvent = postEvent;

// =========================
// QR Scan (Cámara)
// Requiere: <script src="https://unpkg.com/html5-qrcode"></script>
// y <div id="reader"></div>
// =========================
function extractMaterialId(text) {
  const t = String(text || "").trim();

  // "2"
  if (/^\d+$/.test(t)) return Number(t);

  // "material:2" o "material_id:2"
  const m1 = t.match(/material\D*(\d+)/i);
  if (m1) return Number(m1[1]);

  // "id=2"
  const m2 = t.match(/[?&]id=(\d+)/i);
  if (m2) return Number(m2[1]);

  // último número que aparezca
  const m3 = t.match(/(\d+)(?!.*\d)/);
  if (m3) return Number(m3[1]);

  return null;
}

async function getMaterialById(id) {
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api/ra/materials/${id}`, {
    method: "GET",
    headers: headers()
  });
  const data = await res.json().catch(() => null);
  return { status: res.status, data };
}

async function postScanEvent(id, markerText) {
  const baseUrl = getBaseUrl();
  const userEmail = document.getElementById("userEmail").value.trim().toLowerCase();

  const body = {
    material_id: id,
    event_type: "scan",
    user_email: userEmail,
    metadata: { device: "qr-web", marker: markerText }
  };

  const res = await fetch(`${baseUrl}/api/ra/events`, {
    method: "POST",
    headers: { ...headers(), "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  const data = await res.json().catch(() => null);
  return { status: res.status, data };
}

// Anti-repetición (no spamear el mismo QR)
let lastScan = { id: null, ts: 0 };
function isSpam(id) {
  const now = Date.now();
  if (lastScan.id === id && (now - lastScan.ts) < 2500) return true;
  lastScan = { id, ts: now };
  return false;
}

let html5QrCode = null;

async function onScanSuccess(decodedText) {
  console.log("QR DETECTADO:", decodedText);

  const id = Number(decodedText);

  if (!id || isNaN(id)) {
    out("QR inválido");
    return;
  }

  try {
    const baseUrl = document.getElementById("baseUrl").value.trim();
    const apiKey = document.getElementById("apiKey").value.trim();
    const userEmail = document.getElementById("userEmail").value.trim().toLowerCase();

    // 1️⃣ GET material
    const resMat = await fetch(`${baseUrl}/api/ra/materials/${id}`, {
      method: "GET",
      headers: { "X-API-Key": apiKey }
    });

    const mat = {
      status: resMat.status,
      data: await resMat.json()
    };

    // 2️⃣ POST evento
    const body = {
      material_id: id,
      event_type: "scan",
      user_email: userEmail,
      metadata: { device: "web-client", marker: `qr:${id}` }
    };

    const resEv = await fetch(`${baseUrl}/api/ra/events`, {
      method: "POST",
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    const ev = {
      status: resEv.status,
      data: await resEv.json()
    };

    // 3️⃣ Mostrar tarjeta visual
    if (mat.status === 200 && mat.data) {
      const m = mat.data;

      document.getElementById("overlayCard").style.display = "block";
      document.getElementById("matName").textContent = m.name || "Sin nombre";
      document.getElementById("matLab").textContent = m.lab || "-";
      document.getElementById("matLocation").textContent = m.location || "-";
      document.getElementById("matPieces").textContent = m.pieces_qty || "-";
      document.getElementById("matStatus").textContent = m.status || "-";

      const scanStatus = document.getElementById("scanStatus");

      if (ev.status === 201) {
        scanStatus.style.color = "green";
        scanStatus.textContent = "✔ Escaneo registrado correctamente.";
      } else if (ev.status === 403) {
        scanStatus.style.color = "red";
        scanStatus.textContent = "⛔ Usuario con adeudo activo.";
      } else {
        scanStatus.style.color = "orange";
        scanStatus.textContent = "⚠ Evento no registrado.";
      }
    } else {
      out({ error: "Material no encontrado", mat });
    }

  } catch (err) {
    console.error(err);
    out(String(err));
  }
}

async function startCamera() {
  if (!window.Html5Qrcode) {
    out("No cargó Html5Qrcode. Revisa que el CDN esté en index.html.");
    return;
  }

  // Si ya estaba corriendo, no reiniciar
  if (html5QrCode) {
    out({ ok: true, msg: "La cámara ya está activa." });
    return;
  }

  html5QrCode = new Html5Qrcode("reader");

  try {
    await html5QrCode.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 260, height: 260 } },
      onScanSuccess
    );
    out({ ok: true, msg: "Cámara iniciada. Escanea un QR." });
  } catch (e) {
    html5QrCode = null;
    out({ error: "No pude iniciar cámara", detail: String(e) });
  }
}

async function stopCamera() {
  try {
    if (html5QrCode) {
      await html5QrCode.stop();
      await html5QrCode.clear();
      html5QrCode = null;
    }
    out({ ok: true, msg: "Cámara detenida" });
  } catch (e) {
    out({ error: "Error deteniendo cámara", detail: String(e) });
  }
}

// Exponer para onclick
window.startCamera = startCamera;
window.stopCamera = stopCamera;