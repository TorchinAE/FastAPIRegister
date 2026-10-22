// Выпадающие списки модулей на страницах расчёта:
// фильтр по характеристикам (Ном Ток, Напряж., Кл. точн., стац, втыч, выкат, ручн, эл.прив)
// и подсветка модулей цветом их типа материала (цвет задаётся на странице «Типы материалов»).
// Фильтр — общий (renderBar) или свой у строки (slotFilters: какие фильтры — выбираются в «Обязательных строках»).
// Модули приходят уже отсортированными: ном. ток, класс точности, название.
const ModulePicker = (() => {
    const FLAGS = [['stats', 'стац'], ['vtych', 'втыч'], ['vykat', 'выкат'], ['ruchn', 'ручн'], ['el_priv', 'эл.прив']];
    const FILTERS = [['nom_tok', 'Ном Ток'], ['voltage', 'Напряж.'], ['accuracy_class', 'Кл. точн.'], ...FLAGS];
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

    function passes(m, f) {
        if (f.nom_tok && String(m.nom_tok) !== f.nom_tok) return false;
        if (f.voltage && !split(m.voltage).includes(f.voltage)) return false;
        if (f.accuracy_class && !split(m.accuracy_class).includes(f.accuracy_class)) return false;
        return FLAGS.every(([key]) => !f[key] || (f[key] === '1') === !!m[key]);
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
            if (!passes(m, cfg.filters) && String(m.id) !== current) { hidden++; return; }
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
        configs.set(select, {placeholder, allow, filters});
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

    // Значения фильтра из списка модулей; null — флаг (✓/✗)
    function filterValues(key, list) {
        if (key === 'nom_tok') return distinct(list.map(m => m.nom_tok), true);
        if (key === 'voltage' || key === 'accuracy_class') return distinct(list.flatMap(m => split(m[key])));
        return null;
    }

    function filtersHtml(keys, list) {
        return FILTERS.filter(([key]) => keys.includes(key)).map(([key, label]) => {
            const values = filterValues(key, list);
            const options = values
                ? values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('')
                : '<option value="1">✓</option><option value="0">✗</option>';
            return `<label class="mp-filter"><span>${label}</span><select data-filter="${key}">
                <option value="">—</option>${options}</select></label>`;
        }).join('');
    }

    function bindFilters(root, state, onChange) {
        root.querySelectorAll('select[data-filter]').forEach(sel => sel.addEventListener('change', () => {
            state[sel.dataset.filter] = sel.value;
            sel.classList.toggle('active', !!sel.value);
            onChange();
        }));
    }

    function renderBar(bar) {
        if (!bar) return;
        const legend = new Map();
        modules.forEach(m => { if (m.color && m.type_name) legend.set(m.type_name, m.color); });
        bar.innerHTML = `
            <span class="mp-title">Фильтр модулей:</span>
            ${filtersHtml(FILTERS.map(([key]) => key), modules)}
            <button type="button" class="btn btn-ghost btn-sm mp-reset">Сбросить</button>
            ${legend.size ? `<span class="mp-legend">${[...legend].map(([name, c]) =>
                `<span class="mp-chip" style="background:${c};color:${textColor(c)}">${esc(name)}</span>`).join('')}</span>` : ''}`;
        bindFilters(bar, filters, refreshAll);
        bar.querySelector('.mp-reset').addEventListener('click', () => {
            bar.querySelectorAll('select[data-filter]').forEach(sel => { sel.value = ''; sel.classList.remove('active'); });
            Object.keys(filters).forEach(k => { filters[k] = ''; });
            refreshAll();
        });
    }

    // Свои фильтры у select строки: keys — какие показать, значения — из модулей, подходящих в строку
    function slotFilters(container, select, keys) {
        const cfg = configs.get(select);
        cfg.filters = {};
        container.innerHTML = filtersHtml(keys, modules.filter(m => cfg.allow(m, '')));
        bindFilters(container, cfg.filters, () => fill(select));
    }

    function init(data, bar, priceFormatter) {
        modules = data;
        byId = new Map(data.map(m => [m.id, m]));
        if (priceFormatter) fmtPrice = priceFormatter;
        renderBar(bar);
    }

    return {init, attach, slotFilters, refreshAll, color, paint};
})();
