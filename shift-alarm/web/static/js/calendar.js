/**
 * 排班闹钟 - 日历视图
 */

const SHIFT_COLORS = {
    1: '#FFB74D', 2: '#5C6BC0', 3: '#66BB6A',
    4: '#BDBDBD', 5: '#4527A0', 6: '#EF5350',
};

const SHIFT_NAMES = {
    1: '白班', 2: '夜A', 3: '早班',
    4: '休息', 5: '夜B', 6: '值班',
};

const WEEKDAY_NAMES = ['一', '二', '三', '四', '五', '六', '日'];

async function renderCalendar() {
    try {
        const data = await api(`/calendar?year=${STATE.calYear}&month=${STATE.calMonth}`);
        const grid = document.getElementById('calendar-grid');
        document.getElementById('cal-title').textContent =
            `${data.year}年 ${data.month}月`;

        // 表头
        let html = WEEKDAY_NAMES.map(d =>
            `<div class="calendar-day-header">${d}</div>`
        ).join('');

        // 日格
        data.days.forEach(day => {
            const color = SHIFT_COLORS[day.shift_type] || '#999';
            const name = SHIFT_NAMES[day.shift_type] || '?';
            const bgColor = day.in_month
                ? lightenColor(color, 0.7)
                : lightenColor(color, 0.85);

            let cls = 'calendar-day';
            if (!day.in_month) cls += ' other-month';
            if (day.is_today) cls += ' today';
            if (day.is_holiday) cls += ' holiday';

            html += `
                <div class="${cls}"
                     style="background:${bgColor}"
                     title="${day.date}\n${name}${day.is_holiday ? ' (节假日)' : ''}"
                     data-date="${day.date}"
                     data-shift="${day.shift_type}">
                    <span class="day-num">${day.day}</span>
                    <span class="day-label">${name}</span>
                </div>
            `;
        });

        grid.innerHTML = html;

        // 点击某天可以手动覆盖（简化：弹出提示）
        grid.querySelectorAll('.calendar-day').forEach(el => {
            el.addEventListener('click', () => {
                const d = el.dataset.date;
                const s = parseInt(el.dataset.shift);
                if (confirm(`要将 ${d} 的排班改为其他班次吗？`)) {
                    showShiftPicker(d, s);
                }
            });
        });
    } catch (e) {
        console.error('加载日历失败:', e);
    }
}

function lightenColor(hex, factor) {
    // 将 hex 转为更亮的颜色（加白色混合）
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const lr = Math.round(r + (255 - r) * factor);
    const lg = Math.round(g + (255 - g) * factor);
    const lb = Math.round(b + (255 - b) * factor);
    return `rgb(${lr},${lg},${lb})`;
}

async function showShiftPicker(dateStr, currentShift) {
    const names = ['白班', '夜班(A)', '早班', '休息', '夜班(B)', '值班'];
    const types = [1, 2, 3, 4, 5, 6];
    const msg = names.map((n, i) => `${i + 1}. ${n}`).join('\n');
    const choice = prompt(`选择班次：\n${msg}\n当前: ${SHIFT_NAMES[currentShift] || '?'}`, '');
    if (choice && types[parseInt(choice) - 1]) {
        try {
            await api('/schedule/override', {
                method: 'PUT',
                body: JSON.stringify({
                    date: dateStr,
                    shift_type: types[parseInt(choice) - 1],
                }),
            });
            showToast(`已更新 ${dateStr} 排班`, 'success');
            renderCalendar();
        } catch (e) {
            showToast('更新失败', 'error');
        }
    }
}

async function refreshHolidays() {
    const year = new Date().getFullYear();
    try {
        await api(`/holidays/refresh?year=${year}`, { method: 'POST' });
        showToast(`已刷新 ${year} 年节假日数据`, 'success');
        renderCalendar();
        loadDashboard();
    } catch (e) {
        showToast('刷新节假日失败', 'error');
    }
}
