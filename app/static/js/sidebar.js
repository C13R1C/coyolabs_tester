document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const btnCollapse = document.getElementById("btnCollapse");
  const btnToggleSidebar = document.getElementById("btnToggleSidebar");
  const mobileBreakpoint = 768;

  function isMobile() {
    return window.innerWidth <= mobileBreakpoint;
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

  function resetDesktopStateOnMobile() {
    if (isMobile()) {
      sidebar.classList.remove("collapsed");
    } else {
      sidebar.classList.add("collapsed");
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

  /* Cerrar menú al usar una opción */
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobile()) {
        closeMobileSidebar();
      }
    });
  });

  window.addEventListener("resize", resetDesktopStateOnMobile);

  resetDesktopStateOnMobile();
});
