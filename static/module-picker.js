// Выпадающие списки модулей на страницах расчёта:
// фильтр по характеристикам (Ном Ток, Напряж., Кл. точн., стац, втыч, выкат, ручн, эл.прив)
// и подсветка модулей цветом их типа материала (цвет задаётся на странице «Типы материалов»).
// Фильтр — общий (renderBar) или свой у строки (slotFilters: какие фильтры — выбираются в «Обязательных строках»).
// Модули приходят уже отсортированными: ном. ток, класс точности, название.
// Модуль с ценой 0 или с материалом с ценой 0 (m.zero) подсвечивается красным.
// Текстовый фильтр по названию — search(input, select).
const ModulePicker = (() => {
    const FLAGS = [['stats', 'стац'], ['vtych', 'втыч'], ['vykat', 'выкат'], ['ruchn', 'ручн'], ['el_priv', 'эл.прив']];
    const FILTERS = [['nom_tok', 'Ном Ток'], ['voltage', 'Напряж.'], ['accuracy_class', 'Кл. точн.'], ...FLAGS];
    const filters = {};
    const ZERO_COLOR = '#c62828';
    const configs = new WeakMap();
    let modules = [];
    let byId = new Map();
    let fmtPrice = v => v;

    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    // Несколько значений характеристики — через «;» (запятая — десятичная: 0,5/10P, 0,4)
    const split = s => String(s || '').split(';').map(x => x.trim()).filter(Boolean);

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
        if (f.type_id && !typeMatch(m, [parseInt(f.type_id)])) return false;
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
        const text = (cfg.text || '').toLowerCase();
        modules.forEach(m => {
            if (!cfg.allow(m, current)) return;
            const byText = !text || m.name.toLowerCase().includes(text);
            if ((!passes(m, cfg.filters) || !byText) && String(m.id) !== current) { hidden++; return; }
            const opt = new Option((m.zero ? '⚠ ' : '') + optionLabel(m), m.id);
            paint(opt, m.color);
            if (m.zero) { opt.style.color = ZERO_COLOR; opt.style.fontWeight = '600'; }
            select.add(opt);
        });
        select.value = current;
        select.title = hidden ? `Скрыто фильтром: ${hidden}` : '';
        paintSelect(select);
    }

    function paintSelect(select) {
        const m = byId.get(parseInt(select.value));
        paint(select, m ? m.color : '');
        select.classList.toggle('mp-zero', !!(m && m.zero));
    }

    // Модуль с нулевой ценой (сам или материал состава)
    function isZero(moduleId) {
        const m = byId.get(moduleId);
        return !!(m && m.zero);
    }

    // Текстовый фильтр по названию для select (выбранный модуль остаётся в списке)
    function search(input, select) {
        const cfg = configs.get(select);
        input.addEventListener('input', () => {
            cfg.text = input.value.trim();
            fill(select);
            input.classList.toggle('active', !!cfg.text);
        });
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

    // Фильтр «Тип» строки с несколькими типами модулей: types — [{id, name}]
    function typeFilterHtml(types) {
        return `<label class="mp-filter"><span>Тип</span><select data-filter="type_id"><option value="">—</option>${
            types.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></label>`;
    }

    // Свои фильтры у select строки: keys — какие показать, значения — из модулей, подходящих в строку;
    // types — типы модулей строки (больше одного — фильтр «Тип»)
    function slotFilters(container, select, keys, types = []) {
        const cfg = configs.get(select);
        cfg.filters = {};
        container.innerHTML = (types.length > 1 ? typeFilterHtml(types) : '')
            + filtersHtml(keys, modules.filter(m => cfg.allow(m, '')));
        bindFilters(container, cfg.filters, () => fill(select));
    }

    // Подходит ли модуль в строку с типами материалов typeIds: по типу модуля, а модуль без типа —
    // по типам материалов состава (тип ставится автоматически, только если у всех материалов он один)
    function typeMatch(m, typeIds) {
        if (!typeIds.length) return true;
        if (m.type_id) return typeIds.includes(m.type_id);
        return (m.mat_type_ids || []).some(t => typeIds.includes(t));
    }

    // Общие фильтры блока объединённых строк: значение пишется в фильтры каждой строки блока
    // (у строк остаются и свои фильтры)
    function groupFilters(container, selects, keys) {
        const state = {};
        // У строки без своих фильтров — свой объект (не общий фильтр страницы)
        selects.forEach(sel => { const c = configs.get(sel); if (c.filters === filters) c.filters = {}; });
        const allowed = modules.filter(m => selects.some(s => configs.get(s).allow(m, '')));
        container.innerHTML = filtersHtml(keys, allowed);
        bindFilters(container, state, () => selects.forEach(sel => {
            Object.assign(configs.get(sel).filters, state);
            fill(sel);
        }));
    }

    // Общий фильтр блока объединённых строк
    const GROUP_FILTERS = ['nom_tok'];

    // Обязательные строки по блокам объединения (подряд идущие с одним slot.group).
    // entries — [{slot, ...}]; append(entry, target, ownFilters) добавляет строку в target и возвращает её select.
    // Блок из нескольких строк — рамка с общим фильтром «Ном Ток» сверху, остальные фильтры — у каждой строки.
    function renderSlotGroups(target, entries, append) {
        for (let i = 0; i < entries.length;) {
            let j = i + 1;
            while (j < entries.length && entries[j].slot.group === entries[i].slot.group) j++;
            const run = entries.slice(i, j);
            if (run.length === 1) {
                append(run[0], target, run[0].slot.filters);
            } else {
                const box = document.createElement('div');
                box.className = 'calc-slot-group';
                const head = document.createElement('div');
                head.className = 'calc-slot-filters calc-group-filters';
                box.appendChild(head);
                target.appendChild(box);
                const selects = run.map(e => append(e, box, e.slot.filters.filter(k => !GROUP_FILTERS.includes(k))));
                groupFilters(head, selects, GROUP_FILTERS);
            }
            i = j;
        }
    }

    function init(data, bar, priceFormatter) {
        modules = data;
        byId = new Map(data.map(m => [m.id, m]));
        if (priceFormatter) fmtPrice = priceFormatter;
        renderBar(bar);
    }

    return {init, attach, slotFilters, groupFilters, renderSlotGroups, search, refreshAll, color, paint, isZero, typeMatch};
})();
