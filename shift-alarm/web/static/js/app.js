/**
 * 排班闹钟 - 主应用逻辑
 */

// ─── 全局状态 ──────────────────────────────────────
const STATE = {
    workMode: 1,            // 1=正常, 2=特殊
    cycleStartDate: '',
    cycleRefIndex: 0,
    shifts: {},
    cyclePattern: [],
    currentPage: 'dashboard',
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth() + 1,
};

// ─── API 封装 ──────────────────────────────────────

async function api(path, options = {}) {
    const url = '/api' + path;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || '请求失败');
    }
    return res.json();
}

// ─── Toast ─────────────────────────────────────────

function showToast(msg, type = '') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.3s';
        setTimeout(() => el.remove(), 300);
    }, 2500);
}

// ─── 页面导航 ──────────────────────────────────────

function navigateTo(page) {
    STATE.currentPage = page;
    // 更新侧边栏
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });
    // 更新页面
    document.querySelectorAll('.page').forEach(el => {
        el.classList.toggle('active', el.id === `page-${page}`);
    });
    // 加载页面数据
    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'shifts': loadShiftConfig(); break;
        case 'schedule': loadScheduleSetup(); break;
        case 'alarms': loadAlarms(); break;
        case 'settings': loadSettings(); break;
    }
}

// ─── 工作台 ────────────────────────────────────────

async function loadDashboard() {
    try {
        const status = await api('/status');
        STATE.workMode = status.work_mode;
        STATE.cycleStartDate = status.cycle_start_date;
        STATE.cycleRefIndex = status.cycle_reference_index;
        STATE.shifts = status.shifts;

        renderTodayCards(status);
        renderModeCard(status);
        renderCalendar();
    } catch (e) {
        console.error('加载工作台失败:', e);
        showToast('加载失败，请刷新页面', 'error');
    }
}

function renderTodayCards(status) {
    const today = status.today;
    const tomorrow = status.tomorrow;
    const shifts = status.shifts;

    // 今日
    const tShift = shifts[today.shift_type] || {};
    document.getElementById('today-name').textContent =
        tShift.shift_name || today.shift_type;
    document.getElementById('today-time').textContent =
        tShift.time_range || '';
    document.getElementById('today-label').textContent =
        today.is_holiday ? '🎌 法定节假日' : '';
    document.getElementById('card-today').style.borderLeft =
        `4px solid ${getShiftColor(today.shift_type)}`;

    // 明日
    const tmShift = shifts[tomorrow.shift_type] || {};
    document.getElementById('tomorrow-name').textContent =
        tmShift.shift_name || tomorrow.shift_type;
    document.getElementById('tomorrow-time').textContent =
        tmShift.time_range || '';
    document.getElementById('tomorrow-label').textContent =
        tomorrow.is_holiday ? '🎌 法定节假日' : '';
    document.getElementById('card-tomorrow').style.borderLeft =
        `4px solid ${getShiftColor(tomorrow.shift_type)}`;
}

function renderModeCard(status) {
    const modeNames = { 1: '🏢 正常工作表', 2: '🔧 特殊工种' };
    const modeDescs = {
        1: '白班 / 值班 / 休息 · 自动同步法定节假日',
        2: '全部6种班次 · 自定义循环顺序'
    };
    document.getElementById('current-mode').textContent =
        modeNames[status.work_mode] || '未知';
    document.getElementById('mode-desc').textContent =
        modeDescs[status.work_mode] || '';
}

function getShiftColor(type) {
    const colors = {
        1: '#FFB74D', 2: '#5C6BC0', 3: '#66BB6A',
        4: '#BDBDBD', 5: '#4527A0', 6: '#EF5350',
    };
    return colors[type] || '#999';
}

// ─── 应用初始化 ────────────────────────────────────

async function init() {
    // 侧边栏导航
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', () => navigateTo(el.dataset.page));
    });

    // 全局日历按钮
    document.getElementById('cal-prev').addEventListener('click', () => {
        if (STATE.calMonth === 1) {
            STATE.calMonth = 12; STATE.calYear--;
        } else {
            STATE.calMonth--;
        }
        renderCalendar();
    });
    document.getElementById('cal-next').addEventListener('click', () => {
        if (STATE.calMonth === 12) {
            STATE.calMonth = 1; STATE.calYear++;
        } else {
            STATE.calMonth++;
        }
        renderCalendar();
    });
    document.getElementById('cal-today').addEventListener('click', () => {
        const now = new Date();
        STATE.calYear = now.getFullYear();
        STATE.calMonth = now.getMonth() + 1;
        renderCalendar();
    });

    // 全局刷新节假日
    document.getElementById('btn-refresh-holiday').addEventListener('click', refreshHolidays);

    // 加载首页
    await loadDashboard();
}

document.addEventListener('DOMContentLoaded', init);
