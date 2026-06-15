/**
 * 排班闹钟 - 班次配置 / 排班设置 / 闹钟 / 系统设置
 */

// ─── 班次配置页 ────────────────────────────────────

const SHIFT_NAMES_MAP = {
    1: '白班', 2: '夜班(A)', 3: '早班',
    4: '休息', 5: '夜班(B)', 6: '值班',
};

const SHIFT_COLORS_MAP = {
    1: '#FFB74D', 2: '#5C6BC0', 3: '#66BB6A',
    4: '#BDBDBD', 5: '#4527A0', 6: '#EF5350',
};

const SHIFT_ICONS = {
    1: '☀️', 2: '🌙', 3: '🌅', 4: '😴', 5: '🌃', 6: '🛡️',
};

async function loadShiftConfig() {
    try {
        const shifts = await api('/shifts');
        const list = document.getElementById('shift-config-list');

        list.innerHTML = shifts.map(s => {
            const isRest = s.shift_type === 4;
            return `
            <div class="shift-config-card" data-shift-type="${s.shift_type}">
                <div class="shift-config-color" style="background:${s.color}">
                    ${SHIFT_ICONS[s.shift_type] || '📌'}
                </div>
                <div class="shift-config-info">
                    <div class="name">${s.shift_name}</div>
                    <div class="detail">${s.time_range}</div>
                </div>
                <div class="shift-config-controls">
                    ${isRest ? `
                        <span style="color:var(--text-muted);font-size:13px">休息日无需设置时间</span>
                    ` : `
                        <label>开始 <input type="time"
                            data-shift="${s.shift_type}" data-field="start"
                            value="${minutesToTime(s.start_time)}"></label>
                        <label>结束 <input type="time"
                            data-shift="${s.shift_type}" data-field="end"
                            value="${minutesToTime(s.end_time % 1440)}"></label>
                        ${s.end_time >= 1440 ? '<span style="font-size:11px;color:var(--accent)">跨日</span>' : ''}
                    `}
                    <label>提前提醒 <input type="number"
                        data-shift="${s.shift_type}" data-field="reminder"
                        value="${s.reminder}" min="0" max="1440" style="width:60px"> 分钟</label>
                    <button class="btn btn-primary btn-sm"
                        onclick="saveShiftConfig(${s.shift_type})">💾 保存</button>
                </div>
            </div>
            `;
        }).join('');

        // 跨日期复选框事件
        list.querySelectorAll('input[data-field="end"]').forEach(input => {
            const card = input.closest('.shift-config-card');
            const overnightSpan = document.createElement('span');
            overnightSpan.style.cssText = 'font-size:11px;color:var(--accent);margin-left:4px';
            overnightSpan.textContent = '跨日?';
            input.parentElement.appendChild(overnightSpan);
        });
    } catch (e) {
        console.error('加载班次配置失败:', e);
    }
}

async function saveShiftConfig(shiftType) {
    const card = document.querySelector(`.shift-config-card[data-shift-type="${shiftType}"]`);
    if (!card) return;

    const nameEl = card.querySelector('.name');
    const startEl = card.querySelector(`[data-field="start"]`);
    const endEl = card.querySelector(`[data-field="end"]`);
    const reminderEl = card.querySelector(`[data-field="reminder"]`);

    const startTime = startEl ? timeToMinutes(startEl.value) : 0;
    let endTime = endEl ? timeToMinutes(endEl.value) : 0;

    // 如果结束时间 <= 开始时间，视为跨日
    if (endEl && endTime <= startTime && endTime < 720) {
        endTime += 24 * 60; // 加24小时（跨日）
    }

    const body = {
        shift_name: nameEl ? nameEl.textContent.trim() : SHIFT_NAMES_MAP[shiftType],
        start_time: startTime,
        end_time: endTime,
        reminder: reminderEl ? parseInt(reminderEl.value) || 0 : 0,
        is_active: true,
    };

    try {
        await api(`/shifts/${shiftType}`, {
            method: 'PUT',
            body: JSON.stringify(body),
        });
        showToast(`已保存 ${SHIFT_NAMES_MAP[shiftType]} 配置`, 'success');
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

function minutesToTime(minutes) {
    const m = minutes % 1440;
    const h = Math.floor(m / 60);
    const min = m % 60;
    return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
}

function timeToMinutes(timeStr) {
    if (!timeStr) return 0;
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + (m || 0);
}

// ─── 排班设置页 ────────────────────────────────────

async function loadScheduleSetup() {
    // 加载当前状态
    try {
        const status = await api('/status');
        STATE.workMode = status.work_mode;
        STATE.cycleStartDate = status.cycle_start_date;
        STATE.cycleRefIndex = status.cycle_reference_index;

        // 模式选择
        document.querySelector('input[name="work-mode"][value="1"]').checked =
            status.work_mode === 1;
        document.querySelector('input[name="work-mode"][value="2"]').checked =
            status.work_mode === 2;

        // 显示/隐藏循环配置
        document.getElementById('cycle-config-card').style.display =
            status.work_mode === 2 ? '' : 'none';

        // 加载循环顺序
        await loadCyclePattern();

        // 起始日期
        const today = new Date().toISOString().slice(0, 10);
        document.getElementById('input-start-date').value =
            status.cycle_start_date || today;

        updateRefIndexOptions();
        document.getElementById('input-ref-index').value =
            String(status.cycle_reference_index || 0);

        // 预览
        updateCyclePreview();
    } catch (e) {
        console.error('加载排班设置失败:', e);
    }

    // 事件绑定
    document.querySelectorAll('input[name="work-mode"]').forEach(radio => {
        radio.addEventListener('change', async function () {
            const mode = parseInt(this.value);
            document.getElementById('cycle-config-card').style.display =
                mode === 2 ? '' : 'none';
            try {
                await api('/work-mode', {
                    method: 'PUT',
                    body: JSON.stringify({ work_mode: mode }),
                });
                STATE.workMode = mode;
                showToast('工作模式已切换', 'success');
            } catch (e) {
                showToast('切换失败', 'error');
            }
        });
    });

    document.getElementById('btn-save-cycle').addEventListener('click', saveCyclePattern);
    document.getElementById('btn-save-schedule-settings').addEventListener('click', saveScheduleSettings);
    document.getElementById('input-start-date').addEventListener('change', updateCyclePreview);
    document.getElementById('input-ref-index').addEventListener('change', updateCyclePreview);
}

async function loadCyclePattern() {
    try {
        const patterns = await api('/cycle-pattern');
        STATE.cyclePattern = patterns;

        renderCycleBuilder(patterns);
        renderAvailableShifts(patterns);
        updateCyclePreview();
    } catch (e) {
        console.error('加载循环失败:', e);
    }
}

function renderCycleBuilder(patterns) {
    const builder = document.getElementById('cycle-builder');
    builder.innerHTML = patterns.map((p, i) => `
        <span class="cycle-chip" style="background:${SHIFT_COLORS_MAP[p.shift_type] || '#999'}">
            ${i + 1}. ${p.shift_name || SHIFT_NAMES_MAP[p.shift_type]}
            <span class="remove" onclick="removeFromCycle(${i})">×</span>
        </span>
    `).join('');
}

function renderAvailableShifts(patterns) {
    const usedTypes = new Set(patterns.map(p => p.shift_type));
    // 找到已存在的 available 容器或创建新的
    let container = document.getElementById('cycle-available');
    if (!container) {
        container = document.createElement('div');
        container.id = 'cycle-available';
        container.className = 'cycle-available';
        const builder = document.getElementById('cycle-builder');
        builder.parentElement.insertBefore(container, builder.nextSibling);
    }

    container.innerHTML = Object.entries(SHIFT_NAMES_MAP).map(([type, name]) => `
        <span class="cycle-chip-available"
              onclick="addToCycle(${type})"
              style="${usedTypes.includes(parseInt(type)) ? 'opacity:0.4' : ''}">
            + ${name}
        </span>
    `).join('');
}

function addToCycle(shiftType) {
    const p = STATE.cyclePattern;
    p.push({
        position: p.length,
        shift_type: parseInt(shiftType),
        shift_name: SHIFT_NAMES_MAP[shiftType],
        color: SHIFT_COLORS_MAP[shiftType],
    });
    renderCycleBuilder(p);
    renderAvailableShifts(p);
    updateCyclePreview();
}

function removeFromCycle(index) {
    STATE.cyclePattern.splice(index, 1);
    STATE.cyclePattern.forEach((p, i) => p.position = i);
    renderCycleBuilder(STATE.cyclePattern);
    renderAvailableShifts(STATE.cyclePattern);
    updateCyclePreview();
}

async function saveCyclePattern() {
    const patterns = STATE.cyclePattern.map(p => p.shift_type);
    try {
        await api('/cycle-pattern', {
            method: 'PUT',
            body: JSON.stringify({ patterns }),
        });
        showToast('循环顺序已保存', 'success');
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

function updateCyclePreview() {
    const preview = document.getElementById('preview-list');
    if (!STATE.cyclePattern.length) {
        preview.innerHTML = '<span style="color:var(--text-muted);font-size:13px">请先设置循环顺序</span>';
        updateRefIndexOptions();
        return;
    }

    const startDateStr = document.getElementById('input-start-date').value;
    const refIndex = parseInt(document.getElementById('input-ref-index').value) || 0;

    if (!startDateStr) {
        preview.innerHTML = '<span style="color:var(--text-muted);font-size:13px">请先选择起始日期</span>';
        updateRefIndexOptions();
        return;
    }

    const startDate = new Date(startDateStr + 'T00:00:00');
    const cycleLen = STATE.cyclePattern.length;

    let html = '';
    for (let i = 0; i < 14; i++) {
        const d = new Date(startDate);
        d.setDate(d.getDate() + i);
        const idx = (refIndex + i) % cycleLen;
        const shift = STATE.cyclePattern[idx];
        const dateStr = d.toISOString().slice(0, 10);
        html += `
            <div class="preview-item">
                <div class="p-date">${dateStr.slice(5)}</div>
                <div class="p-shift" style="background:${shift.color || '#999'}">${shift.shift_name}</div>
            </div>
        `;
    }
    preview.innerHTML = html;
    updateRefIndexOptions();
}

function updateRefIndexOptions() {
    const sel = document.getElementById('input-ref-index');
    const len = STATE.cyclePattern.length || 6;  // 默认6
    sel.innerHTML = Array.from({ length: len }, (_, i) => {
        const label = STATE.cyclePattern[i]
            ? STATE.cyclePattern[i].shift_name
            : `第 ${i + 1} 个`;
        return `<option value="${i}">第 ${i + 1} 个 (${label})</option>`;
    }).join('');
}

async function saveScheduleSettings() {
    const startDate = document.getElementById('input-start-date').value;
    const refIndex = parseInt(document.getElementById('input-ref-index').value) || 0;

    try {
        await api('/settings', {
            method: 'PUT',
            body: JSON.stringify({
                cycle_start_date: startDate,
                cycle_reference_index: refIndex,
            }),
        });
        STATE.cycleStartDate = startDate;
        STATE.cycleRefIndex = refIndex;
        showToast('排班设置已保存', 'success');
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

// ─── 闹钟列表 ──────────────────────────────────────

async function loadAlarms() {
    try {
        const alarms = await api('/alarms');
        const list = document.getElementById('alarm-list');

        if (!alarms.length) {
            list.innerHTML = '<div class="empty-state">暂无即将触发的闹钟</div>';
            return;
        }

        list.innerHTML = alarms.map(a => `
            <div class="alarm-item">
                <div class="alarm-time">${formatAlarmTime(a.alarm_time)}</div>
                <div class="alarm-shift" style="background:${SHIFT_COLORS_MAP[a.shift_type] || '#999'}">
                    ${a.shift_name}
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('加载闹钟失败:', e);
    }
}

function formatAlarmTime(isoStr) {
    if (!isoStr) return '--';
    const d = new Date(isoStr + (isoStr.includes('Z') ? '' : ''));
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hour = String(d.getHours()).padStart(2, '0');
    const min = String(d.getMinutes()).padStart(2, '0');
    return `${month}/${day} ${hour}:${min}`;
}

// ─── 系统设置 ──────────────────────────────────────

async function loadSettings() {
    try {
        const settings = await api('/settings');
        document.getElementById('input-snooze').value = settings.snooze_minutes || 5;
        document.getElementById('input-volume').value = settings.alarm_volume || 80;
        document.getElementById('volume-display').textContent =
            (settings.alarm_volume || 80) + '%';

        document.getElementById('input-volume').addEventListener('input', function () {
            document.getElementById('volume-display').textContent = this.value + '%';
        });
    } catch (e) {
        console.error('加载设置失败:', e);
    }

    document.getElementById('btn-save-settings').addEventListener('click', saveAppSettings);
    document.getElementById('btn-refresh-holiday2').addEventListener('click', () => {
        const year = parseInt(document.getElementById('input-holiday-year').value) || 2026;
        api(`/holidays/refresh?year=${year}`, { method: 'POST' })
            .then(() => showToast(`已刷新 ${year} 年节假日`, 'success'))
            .catch(() => showToast('刷新失败', 'error'));
    });
}

async function saveAppSettings() {
    try {
        await api('/settings', {
            method: 'PUT',
            body: JSON.stringify({
                snooze_minutes: parseInt(document.getElementById('input-snooze').value) || 5,
                alarm_volume: parseInt(document.getElementById('input-volume').value) || 80,
            }),
        });
        showToast('设置已保存', 'success');
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}
