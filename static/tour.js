(() => {
  const colors = ['#57A6D8', '#55A77B', '#E0B642', '#9A78C5', '#E58C54'];
  const charts = [
    {selector:'#tourPieLast',values:[38,25,17,10,10]},
    {selector:'#tourPieThis',values:[45,30,20,20,25]},
    {selector:'#tourPieNext',values:[50,32,25,24,29]},
  ];

  function sector(cx, cy, radius, start, end) {
    const point = angle => {
      const radians = angle * Math.PI / 180;
      return [cx + radius * Math.cos(radians), cy + radius * Math.sin(radians)];
    };
    const [x1,y1] = point(start), [x2,y2] = point(end);
    const large = end - start > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
  }

  charts.forEach(chart => {
    const svg = document.querySelector(chart.selector);
    if (!svg) return;
    const total = chart.values.reduce((sum, value) => sum + value, 0);
    let angle = -90;
    const paths = chart.values.map((value, index) => {
      const end = angle + value / total * 360;
      const d = sector(100, 100, 92, angle, end);
      angle = end;
      return `<path d="${d}" fill="${colors[index]}"/>`;
    }).join('');
    svg.innerHTML = `<circle cx="100" cy="100" r="94" fill="#EEF3F1"/>${paths}`;
  });

  const scenes = [...document.querySelectorAll('.tour-scene')];
  const steps = [...document.querySelectorAll('.tour-step')];
  const progress = document.querySelector('#tourProgressBar');
  const count = document.querySelector('#tourStepCount');
  const pause = document.querySelector('#pauseTour');
  const next = document.querySelector('#nextStep');
  const previous = document.querySelector('#prevStep');
  const duration = 7200;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let active = 0;
  let playing = !reducedMotion;
  let timer = null;

  function render(index) {
    active = Math.max(0, Math.min(scenes.length - 1, index));
    scenes.forEach((scene, i) => scene.classList.toggle('active', i === active));
    steps.forEach((step, i) => {
      step.classList.toggle('active', i === active);
      if (i === active) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
    progress.style.width = `${((active + 1) / scenes.length) * 100}%`;
    count.textContent = `${String(active + 1).padStart(2, '0')} / ${String(scenes.length).padStart(2, '0')}`;
    next.textContent = active === scenes.length - 1 ? 'Open app →' : 'Next →';
    if (playing && active === scenes.length - 1) playing = false;
    pause.textContent = playing ? 'Ⅱ Pause' : '▶ Play';
    schedule();
  }

  function schedule() {
    clearTimeout(timer);
    if (playing && active < scenes.length - 1) timer = setTimeout(() => render(active + 1), duration);
  }

  steps.forEach(step => step.addEventListener('click', () => render(Number(step.dataset.step))));
  pause.addEventListener('click', () => {
    if (!playing && active === scenes.length - 1) { playing = true; render(0); return; }
    playing = !playing;
    pause.textContent = playing ? 'Ⅱ Pause' : '▶ Play';
    schedule();
  });
  previous.addEventListener('click', () => { playing = false; render(active - 1); });
  next.addEventListener('click', () => {
    if (active === scenes.length - 1) window.location.href = '/';
    else { playing = false; render(active + 1); }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight') { playing = false; render(active + 1); }
    if (event.key === 'ArrowLeft') { playing = false; render(active - 1); }
    if (event.key === 'Escape') window.location.href = '/';
  });
  render(0);
})();
