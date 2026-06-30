(function() {
    const API = {
        status: '/api/status',
        config: '/api/config',
        testToken: '/api/config/test',
        holdings: '/api/holdings',
        uploadHoldings: '/api/holdings/upload',
        dailyReview: '/api/review/daily',
        weeklyReview: '/api/review/weekly'
    };

    let currentHoldings = [];
    let showToken = false;

    async function fetchJSON(url, options = {}) {
        try {
            const res = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                ...options
            });
            return await res.json();
        } catch (e) {
            return { success: false, message: '网络错误' };
        }
    }

    function showToast(message, duration = 2000) {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), duration);
    }

    function formatDate(dateStr) {
        if (!dateStr || dateStr.length !== 8) return dateStr;
        return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async function loadStatus() {
        const data = await fetchJSON(API.status);
        const badge = document.getElementById('mode-badge');
        if (data.mock_mode) {
            badge.textContent = '模拟模式';
            badge.className = 'badge mock';
        } else {
            badge.textContent = '实盘数据';
            badge.className = 'badge real';
        }
        return data;
    }

    function initNav() {
        const navBtns = document.querySelectorAll('.nav-btn');
        const pages = document.querySelectorAll('.page');

        navBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const pageName = btn.dataset.page;
                navBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                pages.forEach(p => p.classList.remove('active'));
                document.getElementById(`page-${pageName}`).classList.add('active');

                if (pageName === 'daily') loadDailyReview();
                if (pageName === 'weekly') loadWeeklyReview();
                if (pageName === 'holdings') loadHoldings();
                if (pageName === 'settings') loadConfig();
            });
        });
    }

    async function loadDailyReview() {
        const loading = document.getElementById('daily-loading');
        const content = document.getElementById('daily-content');
        const errorBox = document.getElementById('daily-error');

        loading.classList.remove('hidden');
        content.classList.add('hidden');
        errorBox.classList.add('hidden');

        const data = await fetchJSON(API.dailyReview);

        loading.classList.add('hidden');

        if (!data.success) {
            document.getElementById('daily-error-msg').textContent = data.message || '加载失败';
            errorBox.classList.remove('hidden');
            return;
        }

        renderDailyReview(data.data);
        content.classList.remove('hidden');
    }

    function renderDailyReview(data) {
        document.getElementById('daily-date').textContent = formatDate(data.trade_date);

        const yesterdayEl = document.getElementById('yesterday-top3');
        const todayEl = document.getElementById('today-top3');

        yesterdayEl.innerHTML = data.yesterday_top3.map(name =>
            `<span class="sector-tag">${escapeHtml(name)}</span>`
        ).join('');

        todayEl.innerHTML = data.today_top3.map((name, i) =>
            `<span class="sector-tag rank-${i + 1}">${escapeHtml(name)}</span>`
        ).join('');

        document.getElementById('daily-changes').textContent = data.changes.join('；');

        const topSectorsEl = document.getElementById('top-sectors');
        topSectorsEl.innerHTML = data.top_sectors.map((s, i) => `
            <div class="sector-rank-item">
                <span class="rank-num ${i < 3 ? 'top' + (i + 1) : ''}">${i + 1}</span>
                <span class="rank-name">${escapeHtml(s.name)}</span>
                <span class="rank-value">${s.close.toFixed(2)}</span>
                <span class="rank-change ${s.change >= 0 ? 'up' : 'down'}">
                    ${s.change >= 0 ? '+' : ''}${s.change.toFixed(2)}%
                </span>
            </div>
        `).join('');

        const emotion = data.emotion;
        document.getElementById('limit-count').textContent = emotion.limit_up_count + '只';
        document.getElementById('max-height').textContent = emotion.max_limit_height + '板';
        document.getElementById('break-rate').textContent = emotion.break_rate + '%';
        document.getElementById('emotion-state').textContent = emotion.emotion_state;

        const holdingEl = document.getElementById('holding-analysis');
        if (data.holding_analysis.length === 0) {
            holdingEl.innerHTML = '<div class="empty-state"><p>暂无持仓，请先添加</p></div>';
        } else {
            holdingEl.innerHTML = data.holding_analysis.map(h => `
                <div class="holding-item">
                    <div class="holding-info">
                        <div class="holding-name">${escapeHtml(h.name)}</div>
                        <div class="holding-meta">
                            <span>${escapeHtml(h.code)}</span>
                            <span>${escapeHtml(h.sector)}</span>
                        </div>
                    </div>
                    <div class="holding-status">
                        <span class="status-badge ${h.matched ? 'matched' : 'mismatched'}">
                            ${h.matched ? '匹配' : '偏离'}
                        </span>
                        <div class="holding-suggest">${h.suggestion}</div>
                    </div>
                </div>
            `).join('');
        }
    }

    async function loadWeeklyReview() {
        const loading = document.getElementById('weekly-loading');
        const content = document.getElementById('weekly-content');
        const errorBox = document.getElementById('weekly-error');

        loading.classList.remove('hidden');
        content.classList.add('hidden');
        errorBox.classList.add('hidden');

        const data = await fetchJSON(API.weeklyReview);

        loading.classList.add('hidden');

        if (!data.success) {
            document.getElementById('weekly-error-msg').textContent = data.message || '加载失败';
            errorBox.classList.remove('hidden');
            return;
        }

        renderWeeklyReview(data.data);
        content.classList.remove('hidden');
    }

    function renderWeeklyReview(data) {
        document.getElementById('weekly-date-range').textContent =
            `${formatDate(data.start_date)} ~ ${formatDate(data.end_date)}`;

        const top3El = document.getElementById('weekly-top3');
        top3El.innerHTML = data.top3.map((name, i) => `
            <div class="podium-item">
                <div class="podium-rank">${i + 1}</div>
                <div class="podium-name">${escapeHtml(name)}</div>
                <div class="podium-bar">TOP${i + 1}</div>
            </div>
        `).join('');

        document.getElementById('lifecycle-stage').textContent = data.lifecycle.stage;
        document.getElementById('lifecycle-evidence').textContent = data.lifecycle.evidence;

        const subEl = document.getElementById('sub-sectors');
        subEl.innerHTML = data.sub_sectors.map(s => `
            <div class="sub-sector-item">
                <span class="sub-sector-name">${escapeHtml(s.name)}</span>
                <span class="sub-sector-stage">${escapeHtml(s.stage)}</span>
            </div>
        `).join('');

        const diagEl = document.getElementById('weekly-holding-diag');
        if (data.holding_diag.length === 0) {
            diagEl.innerHTML = '<div class="empty-state"><p>暂无持仓，请先添加</p></div>';
        } else {
            diagEl.innerHTML = data.holding_diag.map(h => `
                <div class="holding-item">
                    <div class="holding-info">
                        <div class="holding-name">${escapeHtml(h.name)}</div>
                        <div class="holding-meta">
                            <span>${escapeHtml(h.code)}</span>
                            <span>${escapeHtml(h.sector)}</span>
                        </div>
                    </div>
                    <div class="holding-status">
                        <span class="status-badge ${h.in_main ? 'matched' : 'mismatched'}">
                            ${h.in_main ? '主线内' : '偏离'}
                        </span>
                        <div class="holding-suggest">${h.action}</div>
                    </div>
                </div>
            `).join('');
        }
    }

    async function loadHoldings() {
        const data = await fetchJSON(API.holdings);
        currentHoldings = Array.isArray(data) ? data : [];
        renderHoldings();
    }

    function renderHoldings() {
        const listEl = document.getElementById('holdings-list');
        const emptyEl = document.getElementById('holdings-empty');
        const countEl = document.getElementById('holding-count');

        countEl.textContent = currentHoldings.length;

        if (currentHoldings.length === 0) {
            listEl.innerHTML = '';
            emptyEl.classList.remove('hidden');
            return;
        }

        emptyEl.classList.add('hidden');
        listEl.innerHTML = currentHoldings.map((h, i) => `
            <div class="holding-item">
                <div class="holding-info">
                    <div class="holding-name">${escapeHtml(h.name)}</div>
                    <div class="holding-meta">
                        <span>${escapeHtml(h.code || '')}</span>
                        <span>${escapeHtml(h.sector || '')}</span>
                    </div>
                </div>
                <button class="holding-delete" data-index="${i}" title="删除">✕</button>
            </div>
        `).join('');

        listEl.querySelectorAll('.holding-delete').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                currentHoldings.splice(idx, 1);
                await saveHoldings();
                renderHoldings();
                showToast('已删除');
            });
        });
    }

    async function saveHoldings() {
        await fetchJSON(API.holdings, {
            method: 'POST',
            body: JSON.stringify({ holdings: currentHoldings })
        });
    }

    function initHoldingForm() {
        const form = document.getElementById('add-holding-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = document.getElementById('holding-name').value.trim();
            const code = document.getElementById('holding-code').value.trim();
            const sector = document.getElementById('holding-sector').value.trim();

            if (!name || !code || !sector) {
                showToast('请填写完整信息');
                return;
            }

            currentHoldings.push({ name, code, sector });
            await saveHoldings();
            renderHoldings();
            form.reset();
            showToast('添加成功');
        });
    }

    function initFileUpload() {
        const fileInput = document.getElementById('file-upload');
        const resultEl = document.getElementById('upload-result');

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            resultEl.className = 'upload-result';
            resultEl.textContent = '正在解析...';
            resultEl.classList.remove('hidden');

            try {
                const res = await fetch(API.uploadHoldings, {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (data.success) {
                    currentHoldings = data.holdings;
                    renderHoldings();
                    resultEl.className = 'upload-result success';
                    resultEl.textContent = `✓ 成功导入 ${data.count} 条持仓`;
                } else {
                    resultEl.className = 'upload-result error';
                    resultEl.textContent = '✗ ' + (data.message || '导入失败');
                }
            } catch (err) {
                resultEl.className = 'upload-result error';
                resultEl.textContent = '✗ 上传失败：网络错误';
            }

            fileInput.value = '';
            setTimeout(() => resultEl.classList.add('hidden'), 4000);
        });

        const templateLink = document.getElementById('download-template');
        templateLink.addEventListener('click', (e) => {
            e.preventDefault();
            const csv = 'name,code,sector\n上海瀚讯,300762.SZ,商业航天\n贵州茅台,600519.SH,白酒\n';
            const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'holdings_template.csv';
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    function initClearHoldings() {
        document.getElementById('btn-clear-holdings').addEventListener('click', async () => {
            if (!confirm('确定要清空所有持仓吗？')) return;
            currentHoldings = [];
            await saveHoldings();
            renderHoldings();
            showToast('已清空');
        });
    }

    async function loadConfig() {
        const data = await fetchJSON(API.config);
        document.getElementById('tushare-token').value = data.tushare_token || '';
    }

    function initConfigForm() {
        const form = document.getElementById('config-form');
        const tokenInput = document.getElementById('tushare-token');
        const toggleBtn = document.getElementById('btn-toggle-token');
        const testBtn = document.getElementById('btn-test-token');
        const testResult = document.getElementById('token-test-result');

        toggleBtn.addEventListener('click', () => {
            showToken = !showToken;
            tokenInput.type = showToken ? 'text' : 'password';
            toggleBtn.textContent = showToken ? '隐藏' : '显示';
        });

        testBtn.addEventListener('click', async () => {
            const token = tokenInput.value.trim();
            testResult.className = 'test-result';
            testResult.textContent = '正在测试连接...';
            testResult.classList.remove('hidden');

            const data = await fetchJSON(API.testToken, {
                method: 'POST',
                body: JSON.stringify({ tushare_token: token })
            });

            if (data.success) {
                testResult.className = 'test-result success';
                testResult.textContent = '✓ ' + data.message;
            } else {
                testResult.className = 'test-result error';
                testResult.textContent = '✗ ' + data.message;
            }
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const token = tokenInput.value.trim();

            const data = await fetchJSON(API.config, {
                method: 'POST',
                body: JSON.stringify({ tushare_token: token })
            });

            if (data.success) {
                showToast('配置保存成功');
                loadStatus();
            } else {
                showToast('保存失败');
            }
        });
    }

    function initRefreshButtons() {
        document.getElementById('btn-refresh-daily').addEventListener('click', loadDailyReview);
        document.getElementById('btn-refresh-weekly').addEventListener('click', loadWeeklyReview);
    }

    async function init() {
        initNav();
        initHoldingForm();
        initFileUpload();
        initClearHoldings();
        initConfigForm();
        initRefreshButtons();

        await loadStatus();
        await loadDailyReview();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
