document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const btnCollapse = document.getElementById("btnCollapse");
  const btnToggleSidebar = document.getElementById("btnToggleSidebar");
  const mobileBreakpoint = 768;

  let hoverCloseTimer = null;

  function isMobile() {
    return window.innerWidth <= mobileBreakpoint;
  }

  function clearHoverTimer() {
    if (hoverCloseTimer) {
      clearTimeout(hoverCloseTimer);
      hoverCloseTimer = null;
    }
  }

  function closeMobileSidebar() {
    sidebar.classList.remove("mobile-open");
    overlay.classList.remove("show");
    document.body.style.overflow = "";
  }

  function openMobileSidebar() {
    sidebar.classList.add("mobile-open");
    overlay.classList.add("show");
    document.body.style.overflow = "hidden";
  }

  function toggleCollapseDesktop() {
    if (isMobile()) return;
    sidebar.classList.toggle("collapsed");
  }

  function closeSidebarDesktop() {
    if (isMobile()) return;
    sidebar.classList.add("collapsed");
  }

  function openSidebarDesktop() {
    if (isMobile()) return;
    sidebar.classList.remove("collapsed");
  }

  function resetDesktopStateOnMobile() {
    clearHoverTimer();

    if (isMobile()) {
      sidebar.classList.remove("collapsed");
    } else {
      sidebar.classList.remove("mobile-open");
      overlay.classList.remove("show");
      document.body.style.overflow = "";
    }
  }

  if (btnCollapse) {
    btnCollapse.addEventListener("click", toggleCollapseDesktop);
  }

  if (btnToggleSidebar) {
    btnToggleSidebar.addEventListener("click", () => {
      if (sidebar.classList.contains("mobile-open")) {
        closeMobileSidebar();
      } else {
        openMobileSidebar();
      }
    });
  }

  if (overlay) {
    overlay.addEventListener("click", closeMobileSidebar);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMobileSidebar();
    }
  });

  /* Cerrar menú móvil al usar una opción */
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobile()) {
        closeMobileSidebar();
      } else {
        closeSidebarDesktop();
      }
    });
  });

  /* En escritorio: abrir cuando entra el mouse y cerrar cuando sale */
  sidebar.addEventListener("mouseenter", () => {
    if (isMobile()) return;
    clearHoverTimer();
    openSidebarDesktop();
  });

  sidebar.addEventListener("mouseleave", () => {
    if (isMobile()) return;
    clearHoverTimer();
    hoverCloseTimer = setTimeout(() => {
      closeSidebarDesktop();
    }, 220);
  });

  window.addEventListener("resize", resetDesktopStateOnMobile);

  resetDesktopStateOnMobile();
});