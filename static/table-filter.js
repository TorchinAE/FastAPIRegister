// Фильтры и пагинация таблиц-списков на клиенте.
// Сервер отдаёт все строки, фильтр работает по всему списку (с первого символа), страницы — после фильтра.
// Подключение: <table data-filter-table data-per-page="N"> со строкой фильтров <tr class="table-filter">:
//   input.tf-input[data-col]                  — подстрока, без учёта регистра; data-num — без пробелов (тысячи)
//   input.tf-date[data-col][data-type=date-from|date-to] — период по атрибуту data-sort ячейки (ГГГГММДД)
//   select.tf-select[data-col]                — точное совпадение текста ячейки, "__none__" — пустая/«-»
(function () {
    function cellText(row, col) {
        const cell = row.cells[col];
        return cell ? cell.textContent.replace(/\s+/g, ' ').trim() : '';
    }

    function norm(str, num) {
        str = String(str).toLowerCase();
        return num ? str.replace(/\s/g, '').replace(/,/g, '.') : str;
    }

    function readFilters(table) {
        const filters = [];
        table.querySelectorAll('.table-filter input, .table-filter select').forEach(el => {
            const val = el.value.trim();
            if (!val) return;
            const col = parseInt(el.dataset.col);
            if (isNaN(col)) return;
            if (el.classList.contains('tf-date')) {
                filters.push({col, kind: el.dataset.type, val: val.replace(/-/g, '')});
            } else if (el.tagName === 'SELECT') {
                filters.push({col, kind: 'select', val});
            } else {
                const num = 'num' in el.dataset;
                filters.push({col, kind: 'text', num, val: norm(val, num)});
            }
        });
        return filters;
    }

    function matches(row, filters) {
        return filters.every(f => {
            if (f.kind === 'text') return norm(cellText(row, f.col), f.num).includes(f.val);
            if (f.kind === 'select') {
                const t = cellText(row, f.col);
                return f.val === '__none__' ? (t === '' || t === '-') : t === f.val;
            }
            const cell = row.cells[f.col];
            const sort = cell ? cell.dataset.sort || '' : '';
            if (!sort) return false;
            return f.kind === 'date-from' ? sort >= f.val : sort <= f.val;
        });
    }

    function init(table) {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const perPage = parseInt(table.dataset.perPage) || 0;
        const rows = Array.from(tbody.rows).filter(r => !r.classList.contains('empty-row'));
        const wrap = table.closest('.table-wrap') || table;
        const pager = document.createElement('div');
        pager.className = 'pagination';
        wrap.after(pager);
        let page = 1;
        let matched = rows;

        function renderPager(pages) {
            pager.innerHTML = '';
            pager.style.display = pages > 1 ? '' : 'none';
            for (let p = 1; p <= pages; p++) {
                const a = document.createElement('a');
                a.href = '#';
                a.textContent = p;
                if (p === page) a.className = 'active';
                a.addEventListener('click', e => { e.preventDefault(); page = p; render(); });
                pager.appendChild(a);
            }
        }

        function render() {
            const pages = perPage ? Math.max(1, Math.ceil(matched.length / perPage)) : 1;
            if (page > pages) page = pages;
            const start = perPage ? (page - 1) * perPage : 0;
            const end = perPage ? start + perPage : matched.length;
            const visible = new Set(matched.slice(start, end));
            const matchedSet = new Set(matched);
            rows.forEach(r => {
                r.dataset.matched = matchedSet.has(r) ? '1' : '0';
                r.style.display = visible.has(r) ? '' : 'none';
            });
            renderPager(pages);
            table.dispatchEvent(new CustomEvent('table-filtered', {detail: {matched}}));
        }

        function apply() {
            const filters = readFilters(table);
            matched = filters.length ? rows.filter(r => matches(r, filters)) : rows;
            page = 1;
            render();
        }

        table.querySelectorAll('.table-filter input, .table-filter select').forEach(el => {
            el.addEventListener(el.tagName === 'SELECT' || el.type === 'date' ? 'change' : 'input', apply);
        });
        table.tableFilter = {
            apply,
            reset() {
                table.querySelectorAll('.table-filter input, .table-filter select').forEach(el => { el.value = ''; });
                apply();
            },
            // Строки, прошедшие фильтр (на всех страницах)
            matchedRows: () => matched.filter(r => r.isConnected),
        };
        apply();
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('table[data-filter-table]').forEach(init);
    });
})();
