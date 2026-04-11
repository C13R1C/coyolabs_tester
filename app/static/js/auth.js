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
  const registerEmail = document.getElementById("email_reg");
  const emailRegHint = document.getElementById("emailRegHint");
  const registerForm = document.getElementById("registerForm");
  const toggleForgotPassword = document.getElementById("toggleForgotPassword");
  const forgotPasswordPanel = document.getElementById("forgotPasswordPanel");
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
      if (forgotPasswordPanel) forgotPasswordPanel.setAttribute("hidden", "");
      if (toggleForgotPassword) {
        toggleForgotPassword.setAttribute("aria-expanded", "false");
        toggleForgotPassword.textContent = "¿Olvidaste tu contraseña?";
      }
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

  const institutionalEmailRe = /^([0-9]{8}|[A-Za-z0-9._%+-]+)@utpn\.edu\.mx$/;
  const validateRegisterEmail = () => {
    if (!registerEmail || !emailRegHint) return true;

    const raw = registerEmail.value || "";
    const email = raw.trim();
    if (raw !== email) {
      registerEmail.value = email;
    }

    if (!email) {
      registerEmail.setCustomValidity("");
      emailRegHint.textContent = "";
      emailRegHint.className = "hint";
      return true;
    }

    const ok = institutionalEmailRe.test(email);
    registerEmail.setCustomValidity(
      ok ? "" : "Usa matrícula@utpn.edu.mx o nombre.apellido@utpn.edu.mx"
    );
    emailRegHint.textContent = ok
      ? "✅ Correo institucional válido."
      : "❌ Usa matrícula@utpn.edu.mx o nombre.apellido@utpn.edu.mx";
    emailRegHint.className = ok ? "hint good" : "hint bad";
    return ok;
  };

  registerEmail?.addEventListener("input", validateRegisterEmail);
  registerEmail?.addEventListener("blur", validateRegisterEmail);

  registerForm?.addEventListener("submit", (e) => {
    const isEmailOk = validateRegisterEmail();
    const isConfirmOk = validateConfirm();
    if (!isEmailOk || !isConfirmOk || !registerForm.checkValidity()) {
      e.preventDefault();
      if (!isEmailOk || !registerEmail?.checkValidity()) {
        registerEmail?.focus();
        registerEmail?.reportValidity();
      } else {
        pw2?.focus();
      }
    }
  });

  toggleForgotPassword?.addEventListener("click", () => {
    if (!forgotPasswordPanel) return;
    const isHidden = forgotPasswordPanel.hasAttribute("hidden");
    if (isHidden) {
      forgotPasswordPanel.removeAttribute("hidden");
      forgotPasswordPanel.querySelector("input")?.focus();
      toggleForgotPassword.setAttribute("aria-expanded", "true");
      toggleForgotPassword.textContent = "Ocultar recuperación";
    } else {
      forgotPasswordPanel.setAttribute("hidden", "");
      toggleForgotPassword.setAttribute("aria-expanded", "false");
      toggleForgotPassword.textContent = "¿Olvidaste tu contraseña?";
    }
  });

  authNotifications.forEach((notification) => {
    const closeBtn = notification.querySelector(".notification__close");
    closeBtn?.addEventListener("click", () => {
      notification.remove();
    });
  });
  
})();
