(() => {
  const dialog = document.getElementById('image-viewer');
  if (!dialog) return;
  const image = dialog.querySelector('img');
  const caption = document.getElementById('viewer-caption');
  let origin = null;
  document.querySelectorAll('.shot-open').forEach((button) => {
    button.addEventListener('click', () => {
      origin = button;
      const thumbnail = button.querySelector('img');
      image.src = button.dataset.full;
      image.alt = thumbnail.alt;
      caption.textContent = button.dataset.caption || thumbnail.alt;
      document.documentElement.classList.add('image-viewer-open');
      dialog.showModal();
    });
  });
  dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('image-viewer-open');
    image.removeAttribute('src');
    if (origin) origin.focus({ preventScroll: true });
  });
})();
