// Выпадающие списки модулей на страницах расчёта:
// фильтр по характеристикам (Ном Ток, Напряж., Кл. точн., стац, втыч, выкат, ручн, эл.прив)
// и подсветка модулей цветом их типа материала (цвет задаётся на странице «Типы материалов»).
// Модули приходят уже отсортированными: ном. ток, класс точности, название.
const ModulePicker = (() => {
    const FLAGS = [['stats', 'стац'], ['vtych', 'втыч'], ['vykat', 'выкат'], ['ruchn', 'ручн'], ['el_priv', 'эл.прив']];
    const filters = {};
    const configs = new WeakMap();
    let modules = [];
    let byId = new Map();
    let fmtPrice = v => v;

    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    const split = s => String(s || '').split(',').map(x => x.trim()).filter(Boolean);

    // Тёмный фон — белый текст
    function textColor(hex) {
        const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
        if (!m) return '';
        const [r, g, b] = m.slice(1).map(x => parseInt(x, 16));
        return (r * 299 + g * 587 + b * 114) / 1000 < 140 ? '#fff' : '#000';
    }

    function paint(el, color) {
        el.style.backgroundColor = color || '';
        el.style.color = color ? textColor(color) : '';
    }

    function passes(m) {
        if (filters.nom_tok && String(m.nom_tok) !== filters.nom_tok) return false;
        if (filters.voltage && !split(m.voltage).includes(filters.voltage)) return false;
        if (filters.accuracy_class && !split(m.accuracy_class).includes(filters.accuracy_class)) return false;
        return FLAGS.every(([key]) => !filters[key] || (filters[key] === '1') === !!m[key]);
    }

    function optionLabel(m) {
        return `${m.name} (${fmtPrice(m.price)})`;
    }

    // Заполняет select модулями: allow(m, current) — подходит ли модуль (тип строки), текущий модуль остаётся всегда
    function fill(select) {
        const cfg = configs.get(select);
        const current = select.value;
        select.innerHTML = '';
        select.add(new Option(cfg.placeholder, ''));
        let hidden = 0;
        modules.forEach(m => {
            if (!cfg.allow(m, current)) return;
            if (!passes(m) && String(m.id) !== current) { hidden++; return; }
            const opt = new Option(optionLabel(m), m.id);
            paint(opt, m.color);
            select.add(opt);
        });
        select.value = current;
        select.title = hidden ? `Скрыто фильтром: ${hidden}` : '';
        paintSelect(select);
    }

    function paintSelect(select) {
        const m = byId.get(parseInt(select.value));
        paint(select, m ? m.color : '');
    }

    function attach(select, {placeholder = '-- Модуль --', allow = () => true} = {}) {
        configs.set(select, {placeholder, allow});
        select.dataset.modulePicker = '1';
        select.addEventListener('change', () => paintSelect(select));
        // Значение выставлено из кода — перекрасить
        select.addEventListener('picker-paint', () => paintSelect(select));
        fill(select);
    }

    function refreshAll() {
        document.querySelectorAll('select[data-module-picker]').forEach(s => { if (configs.has(s)) fill(s); });
    }

    function color(moduleId) {
        const m = byId.get(moduleId);
        return m ? m.color : null;
    }

    function distinct(values, numeric) {
        const list = [...new Set(values.filter(v => v !== '' && v !== null && v !== undefined && v !== 0))];
        return numeric ? list.sort((a, b) => a - b) : list.sort((a, b) => String(a).localeCompare(String(b), 'ru'));
    }

    function selectHtml(key, label, values) {
        return `<label class="mp-filter"><span>${label}</span><select data-filter="${key}">
            <option value="">—</option>${values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('')}
        </select></label>`;
    }

    function renderBar(bar) {
        if (!bar) return;
        const noms = distinct(modules.map(m => m.nom_tok), true);
        const volts = distinct(modules.flatMap(m => split(m.voltage)));
        const accs = distinct(modules.flatMap(m => split(m.accuracy_class)));
        const legend = new Map();
        modules.forEach(m => { if (m.color && m.type_name) legend.set(m.type_name, m.color); });
        bar.innerHTML = `
            <span class="mp-title">Фильтр модулей:</span>
            ${selectHtml('nom_tok', 'Ном Ток', noms)}
            ${selectHtml('voltage', 'Напряж.', volts)}
            ${selectHtml('accuracy_class', 'Кл. точн.', accs)}
            ${FLAGS.map(([key, label]) => `<label class="mp-filter"><span>${label}</span><select data-filter="${key}">
                <option value="">—</option><option value="1">✓</option><option value="0">✗</option></select></label>`).join('')}
            <button type="button" class="btn btn-ghost btn-sm mp-reset">Сбросить</button>
            ${legend.size ? `<span class="mp-legend">${[...legend].map(([name, c]) =>
                `<span class="mp-chip" style="background:${c};color:${textColor(c)}">${esc(name)}</span>`).join('')}</span>` : ''}`;
        bar.querySelectorAll('select[data-filter]').forEach(sel => sel.addEventListener('change', () => {
            filters[sel.dataset.filter] = sel.value;
            sel.classList.toggle('active', !!sel.value);
            refreshAll();
        }));
        bar.querySelector('.mp-reset').addEventListener('click', () => {
            bar.querySelectorAll('select[data-filter]').forEach(sel => { sel.value = ''; sel.classList.remove('active'); });
            Object.keys(filters).forEach(k => { filters[k] = ''; });
            refreshAll();
        });
    }

    function init(data, bar, priceFormatter) {
        modules = data;
        byId = new Map(data.map(m => [m.id, m]));
        if (priceFormatter) fmtPrice = priceFormatter;
        renderBar(bar);
    }

    return {init, attach, refreshAll, color, paint};
})();
