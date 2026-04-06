(function () {
  const panel = document.getElementById('user-panel');
  const userTrigger = document.getElementById('user-trigger');

  if (panel && userTrigger) {
    const applyUserState = (open) => {
      panel.classList.toggle('open', open);
      panel.hidden = !open;
      localStorage.setItem('student:user-panel-open', open ? '1' : '0');
    };

    applyUserState(localStorage.getItem('student:user-panel-open') === '1');

    userTrigger.addEventListener('click', (event) => {
      event.stopPropagation();
      applyUserState(!panel.classList.contains('open'));
    });

    document.addEventListener('click', (event) => {
      if (!panel.contains(event.target) && !userTrigger.contains(event.target)) {
        applyUserState(false);
      }
    });
  }

  const topLinksWrapper = document.getElementById('top-links-wrapper');
  const toggleTopLinks = document.getElementById('toggle-top-links');

  if (topLinksWrapper && toggleTopLinks) {
    const applyTopLinks = (visible) => {
      topLinksWrapper.classList.toggle('visible', visible);
      topLinksWrapper.classList.remove('collapsed-by-default');
      localStorage.setItem('student:top-links-collapsed', visible ? '0' : '1');
      toggleTopLinks.textContent = visible ? '×' : '＝';
    };

    const collapsed = localStorage.getItem('student:top-links-collapsed') === '1';
    applyTopLinks(!collapsed);

    toggleTopLinks.addEventListener('click', () => {
      applyTopLinks(!topLinksWrapper.classList.contains('visible'));
    });
  }
})();
