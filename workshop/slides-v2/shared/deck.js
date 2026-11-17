/* Breaking the Cloud — Shared Deck JS (v1)
   Navigation + hash persistence + animated stat counters + bar reveals. */
(function () {
  const slides = document.querySelectorAll('.slide');
  const total = slides.length;
  const totEl = document.getElementById('tot');
  const curEl = document.getElementById('cur');
  const prog = document.getElementById('prog');
  if (totEl) totEl.textContent = total;

  let cur = Math.max(0, Math.min(total - 1, parseInt(location.hash.replace('#', '')) - 1 || 0));
  slides.forEach((s) => s.classList.remove('active'));
  slides[cur].classList.add('active');

  function animateStats(slide) {
    slide.querySelectorAll('.stat .n[data-to]').forEach((el) => {
      const to = parseFloat(el.dataset.to);
      const suffix = el.dataset.suffix || '';
      const prefix = el.dataset.prefix || '';
      const dur = 900;
      const start = performance.now();
      function step(t) {
        const k = Math.min(1, (t - start) / dur);
        const eased = 1 - Math.pow(1 - k, 3);
        const val = to % 1 === 0 ? Math.round(to * eased) : (to * eased).toFixed(1);
        el.textContent = prefix + val + suffix;
        if (k < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
    // reveal bars
    slide.querySelectorAll('.bar-fill[data-w]').forEach((el) => {
      el.style.width = '0%';
      requestAnimationFrame(() => { el.style.width = el.dataset.w + '%'; });
    });
  }

  function render() {
    if (curEl) curEl.textContent = cur + 1;
    if (prog) prog.style.width = ((cur + 1) / total * 100) + '%';
    history.replaceState(null, '', '#' + (cur + 1));
    animateStats(slides[cur]);
  }
  render();

  function show(n) {
    slides[cur].classList.remove('active');
    cur = (n + total) % total;
    slides[cur].classList.add('active');
    render();
  }
  window.nav = (d) => show(cur + d);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'Enter') { e.preventDefault(); show(cur + 1); }
    if (e.key === 'ArrowLeft' || e.key === 'Backspace') { e.preventDefault(); show(cur - 1); }
    if (e.key === 'Home') { e.preventDefault(); show(0); }
    if (e.key === 'End') { e.preventDefault(); show(total - 1); }
  });
  let tsx = 0;
  document.addEventListener('touchstart', (e) => { tsx = e.touches[0].clientX; });
  document.addEventListener('touchend', (e) => {
    const d = tsx - e.changedTouches[0].clientX;
    if (Math.abs(d) > 50) show(cur + (d > 0 ? 1 : -1));
  });
})();
