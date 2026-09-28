document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-filter-list]').forEach(root => {
    const rows = [...root.querySelectorAll('[data-filter-item]')];
    const controls = [...root.querySelectorAll('[data-filter]')];
    const counter = root.querySelector('[data-result-count]');
    const empty = root.querySelector('[data-no-results]');
    function update() {
      let visible = 0;
      for (const row of rows) {
        const show = controls.every(control => {
          const value = control.value.trim().toLocaleLowerCase();
          if (!value || value === 'all') return true;
          if (control.dataset.filter === 'search') return row.textContent.toLocaleLowerCase().includes(value);
          return (row.dataset[control.dataset.filter] || '').toLocaleLowerCase().split('|').includes(value);
        });
        row.hidden = !show;
        if (show) visible++;
      }
      if (counter) counter.textContent = `${visible} ${visible === 1 ? root.dataset.singular : root.dataset.plural}`;
      if (empty) empty.hidden = visible !== 0 || rows.length === 0;
    }
    controls.forEach(control => { control.addEventListener('input', update); control.addEventListener('change', update); });
    update();
  });
  document.querySelectorAll('.copy-citation').forEach(button => {
    button.addEventListener('click', async () => {
      const citation = document.getElementById(button.dataset.citation);
      if (!citation) return;
      try {
        await navigator.clipboard.writeText(citation.innerText.trim());
        button.textContent = 'Copied';
      } catch (_) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(citation);
        selection.removeAllRanges(); selection.addRange(range);
        button.textContent = 'Citation selected — copy with your keyboard';
      }
      const status = document.getElementById('copy-status');
      if (status) status.textContent = button.textContent;
      setTimeout(() => { button.textContent = 'Copy citation'; }, 3500);
    });
  });
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
});

