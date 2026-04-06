(() => {
  const body = document.body;

  const toRegister = document.getElementById("toRegister");
  const toLogin = document.getElementById("toLogin");

  const title = document.getElementById("title");
  const subtitle = document.getElementById("subtitle");

  const overlay = document.querySelector(".forms-overlay");

  // Register password confirm
  const pw = document.getElementById("password_reg");
  const pw2 = document.getElementById("confirm_password_reg");
  const pwHint = document.getElementById("pwHint");
  const registerForm = document.getElementById("registerForm");
  const verifyEmailBox = document.getElementById("verifyEmailBox");
  const toggleForgotPassword = document.getElementById("toggleForgotPassword");
  const forgotPasswordPanel = document.getElementById("forgotPasswordPanel");
  const toggleChangeEmail = document.getElementById("toggleChangeEmail");
  const changeEmailPanel = document.getElementById("changeEmailPanel");
  const changeEmailInput = document.getElementById("change_email_input");
  const saveAndResendBtn = document.getElementById("saveAndResendBtn");
  const changeEmailStatus = document.getElementById("changeEmailStatus");
  const authNotifications = document.querySelectorAll(".auth-notification-stack .notification");

  // Helpers
  const pulseOverlay = () => {
    if (!overlay) return;
    overlay.classList.remove("pulse");
    // reflow para reiniciar animación
    void overlay.offsetWidth;
    overlay.classList.add("pulse");
  };

  const setMode = (mode) => {
    if (mode === "register") {
      body.classList.remove("mode-login");
      body.classList.add("mode-register");
      title.textContent = "Registro institucional";
      subtitle.textContent = "CoyoLabs Universidad — Crear cuenta";
    } else {
      body.classList.remove("mode-register");
      body.classList.add("mode-login");
      title.textContent = "Iniciar sesión";
      subtitle.textContent = "CoyoLabs Universidad — Acceso institucional";
    }
    pulseOverlay();
  };

  // Modo inicial según clase del body
  if (body.classList.contains("mode-register")) setMode("register");
  else setMode("login");

  // Switch buttons
  toRegister?.addEventListener("click", () => setMode("register"));
  toLogin?.addEventListener("click", () => setMode("login"));

  // Toggle password (ojito)
  const toggleBtns = document.querySelectorAll(".toggle-pass[data-toggle]");
  toggleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-toggle");
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.getAttribute("type") === "password";
      input.setAttribute("type", isPassword ? "text" : "password");

      btn.classList.toggle("is-on", isPassword);
      btn.setAttribute("aria-label", isPassword ? "Ocultar contraseña" : "Mostrar contraseña");
    });
  });

  // Confirm password validation (solo en register)
  const validateConfirm = () => {
    if (!pw || !pw2 || !pwHint) return true;

    const a = pw.value || "";
    const b = pw2.value || "";

    // No molestes si aún no teclea
    if (!a && !b) {
      pwHint.textContent = "";
      pwHint.className = "hint";
      return true;
    }

    if (b.length === 0) {
      pwHint.textContent = "";
      pwHint.className = "hint";
      return true;
    }

    const ok = a === b;
    pwHint.textContent = ok ? "✅ Las contraseñas coinciden" : "❌ Las contraseñas no coinciden";
    pwHint.className = ok ? "hint good" : "hint bad";

    return ok;
  };

  pw?.addEventListener("input", validateConfirm);
  pw2?.addEventListener("input", validateConfirm);

  registerForm?.addEventListener("submit", (e) => {
    if (!validateConfirm()) {
      e.preventDefault();
      pw2?.focus();
    }
  });

  const setChangeEmailStatus = (message, kind = "") => {
    if (!changeEmailStatus) return;
    changeEmailStatus.textContent = message || "";
    changeEmailStatus.className = kind ? `hint ${kind}` : "hint";
  };

  const hasPendingVerifyEmail = Boolean((verifyEmailBox?.dataset.pendingEmail || "").trim());
  if (!hasPendingVerifyEmail && verifyEmailBox) {
    verifyEmailBox.style.display = "none";
  } else if (changeEmailInput && verifyEmailBox?.dataset.pendingEmail) {
    changeEmailInput.value = verifyEmailBox.dataset.pendingEmail;
  }

  toggleChangeEmail?.addEventListener("click", () => {
    if (!changeEmailPanel) return;
    const isHidden = changeEmailPanel.hasAttribute("hidden");
    if (isHidden) {
      changeEmailPanel.removeAttribute("hidden");
      changeEmailInput?.focus();
    } else {
      changeEmailPanel.setAttribute("hidden", "");
    }
  });

  toggleForgotPassword?.addEventListener("click", () => {
    if (!forgotPasswordPanel) return;
    const isHidden = forgotPasswordPanel.hasAttribute("hidden");
    if (isHidden) {
      forgotPasswordPanel.removeAttribute("hidden");
      forgotPasswordPanel.querySelector("input")?.focus();
    } else {
      forgotPasswordPanel.setAttribute("hidden", "");
    }
  });

  saveAndResendBtn?.addEventListener("click", async () => {
    const email = (changeEmailInput?.value || "").trim().toLowerCase();
    const csrfToken = verifyEmailBox?.dataset.csrfToken || "";

    if (!email) {
      setChangeEmailStatus("Ingresa un correo institucional válido.", "bad");
      return;
    }

    saveAndResendBtn.disabled = true;
    setChangeEmailStatus("Actualizando...");

    try {
      const response = await fetch("/auth/change-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ email }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message = data?.error || "No se pudo actualizar el correo.";
        setChangeEmailStatus(message, "bad");
        return;
      }

      verifyEmailBox.dataset.pendingEmail = email;
      setChangeEmailStatus("Correo actualizado y código reenviado", "good");
      if (changeEmailPanel) {
        changeEmailPanel.setAttribute("hidden", "");
      }
    } catch (_err) {
      setChangeEmailStatus("Error de red. Intenta de nuevo.", "bad");
    } finally {
      saveAndResendBtn.disabled = false;
    }
  });

  authNotifications.forEach((notification) => {
    const closeBtn = notification.querySelector(".notification__close");
    closeBtn?.addEventListener("click", () => {
      notification.remove();
    });
  });
  
})();
