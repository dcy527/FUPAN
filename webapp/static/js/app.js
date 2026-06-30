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
        if (data.top3.length === 0) {
            top3El.innerHTML = '<div class="empty-state" style="width:100%"><p>暂无数据</p></div>';
        } else {
            top3El.innerHTML = data.top3.map((name, i) => `
                <div class="podium-item">
                    <div class="podium-rank">${i + 1}</div>
                    <div class="podium-name">${escapeHtml(name)}</div>
                    <div class="podium-bar">TOP${i + 1}</div>
                </div>
            `).join('');
        }

        document.getElementById('lifecycle-stage').textContent = data.lifecycle.stage;
        document.getElementById('lifecycle-evidence').textContent = data.lifecycle.evidence;

        const subEl = document.getElementById('sub-sectors');
        if (data.sub_sectors.length === 0) {
            subEl.innerHTML = '<div class="empty-state"><p>暂无数据</p></div>';
        } else {
            subEl.innerHTML = data.sub_sectors.map(s => `
                <div class="sub-sector-item">
                    <span class="sub-sector-name">${escapeHtml(s.name)}</span>
                    <span class="sub-sector-stage">${escapeHtml(s.stage)}</span>
                </div>
            `).join('');
        }

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
        updateSummary();
    }

    function calculatePnL(holding) {
        if (!holding.amount || !holding.cost || !holding.current_price) {
            return { pnl: 0, pnl_rate: 0 };
        }
        const pnl = (holding.current_price - holding.cost) * holding.amount;
        const pnl_rate = ((holding.current_price - holding.cost) / holding.cost * 100);
        return { pnl: pnl.toFixed(2), pnl_rate: pnl_rate.toFixed(2) };
    }

    function updateSummary() {
        let totalAmount = 0;
        let totalValue = 0;
        let totalCost = 0;

        currentHoldings.forEach(h => {
            const amount = parseFloat(h.amount) || 0;
            const cost = parseFloat(h.cost) || 0;
            const current = parseFloat(h.current_price) || 0;
            totalAmount += amount;
            totalValue += amount * current;
            totalCost += amount * cost;
        });

        const totalPnl = totalValue - totalCost;
        
        document.getElementById('total-amount').textContent = totalAmount.toLocaleString();
        document.getElementById('total-value').textContent = '¥' + totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        const pnlEl = document.getElementById('total-pnl');
        pnlEl.textContent = (totalPnl >= 0 ? '+' : '') + '¥' + totalPnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        pnlEl.className = 'summary-value ' + (totalPnl >= 0 ? 'positive' : 'negative');
    }

    function renderHoldings() {
        const listEl = document.getElementById('holdings-list');
        const emptyEl = document.getElementById('holdings-empty');
        const countEl = document.getElementById('holding-count');

        countEl.textContent = currentHoldings.length;

        if (currentHoldings.length === 0) {
            listEl.innerHTML = '';
            emptyEl.classList.remove('hidden');
            updateSummary();
            return;
        }

        emptyEl.classList.add('hidden');
        listEl.innerHTML = currentHoldings.map((h, i) => {
            const { pnl, pnl_rate } = calculatePnL(h);
            const pnlClass = parseFloat(pnl) >= 0 ? 'positive' : 'negative';
            const pnlSign = parseFloat(pnl) >= 0 ? '+' : '';
            
            return `
            <div class="holding-card">
                <button class="holding-card-edit" data-index="${i}" title="编辑">✎</button>
                <button class="holding-card-delete" data-index="${i}" title="删除">✕</button>
                <div class="holding-card-header">
                    <div>
                        <div class="holding-card-name">${escapeHtml(h.name)}</div>
                        <div class="holding-card-code">${escapeHtml(h.code || '')}</div>
                    </div>
                    <div class="holding-card-pnl">
                        <div class="holding-card-pnl-value ${pnlClass}">${pnlSign}¥${parseFloat(pnl).toLocaleString()}</div>
                        <div class="holding-card-pnl-rate ${pnlClass}">${pnlSign}${pnl_rate}%</div>
                    </div>
                </div>
                <div class="holding-card-body">
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">持仓数量</div>
                        <div class="holding-card-item-value">${(parseFloat(h.amount) || 0).toLocaleString()}</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">成本价</div>
                        <div class="holding-card-item-value">¥${parseFloat(h.cost || 0).toFixed(2)}</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">当前价</div>
                        <div class="holding-card-item-value">¥${parseFloat(h.current_price || 0).toFixed(2)}</div>
                    </div>
                </div>
                ${h.sector ? `<span class="holding-card-sector">${escapeHtml(h.sector)}</span>` : ''}
            </div>
        `}).join('');

        listEl.querySelectorAll('.holding-card-delete').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                if (confirm('确定要删除这条持仓吗？')) {
                    currentHoldings.splice(idx, 1);
                    await saveHoldings();
                    renderHoldings();
                    showToast('已删除');
                }
            });
        });

        listEl.querySelectorAll('.holding-card-edit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                const h = currentHoldings[idx];
                document.getElementById('holding-name').value = h.name || '';
                document.getElementById('holding-code').value = h.code || '';
                document.getElementById('holding-amount').value = h.amount || '';
                document.getElementById('holding-cost').value = h.cost || '';
                document.getElementById('holding-current').value = h.current_price || '';
                document.getElementById('holding-sector').value = h.sector || '';
                document.getElementById('holding-pnl').value = h.pnl || '';
                document.getElementById('holding-date').value = h.buy_date || '';
                currentHoldings.splice(idx, 1);
                saveHoldings();
                renderHoldings();
                document.getElementById('holding-name').focus();
                showToast('编辑模式：修改后点击添加即可更新');
            });
        });

        updateSummary();
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
            
            if (!name || !code) {
                showToast('请填写股票名称和代码');
                return;
            }

            const holding = {
                name: name,
                code: code,
                amount: parseFloat(document.getElementById('holding-amount').value) || 0,
                cost: parseFloat(document.getElementById('holding-cost').value) || 0,
                current_price: parseFloat(document.getElementById('holding-current').value) || 0,
                sector: document.getElementById('holding-sector').value.trim(),
                pnl: parseFloat(document.getElementById('holding-pnl').value) || 0,
                buy_date: document.getElementById('holding-date').value
            };

            currentHoldings.push(holding);
            await saveHoldings();
            renderHoldings();
            form.reset();
            showToast('添加成功');
        });

        document.getElementById('btn-fetch-price').addEventListener('click', async () => {
            const code = document.getElementById('holding-code').value.trim();
            if (!code) {
                showToast('请先输入股票代码');
                return;
            }
            showToast('正在获取价格...');
            const data = await fetchJSON(`/api/price?code=${encodeURIComponent(code)}`);
            if (data.success && data.price) {
                document.getElementById('holding-current').value = data.price.toFixed(2);
                showToast(`获取成功：¥${data.price.toFixed(2)}`);
            } else {
                showToast('获取价格失败');
            }
        });
    }

    function initFileUpload() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
            });
        });

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

        const imageInput = document.getElementById('image-upload');
        const previewEl = document.getElementById('image-preview');
        const imageResultEl = document.getElementById('image-result');

        imageInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = async (e) => {
                previewEl.innerHTML = `<img src="${e.target.result}" alt="预览">`;
                previewEl.classList.remove('hidden');
                
                imageResultEl.className = 'image-result';
                imageResultEl.textContent = '正在识别图片中的持仓信息...';
                imageResultEl.classList.remove('hidden');

                const formData = new FormData();
                formData.append('image', file);

                try {
                    const res = await fetch('/api/holdings/ocr', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();

                    if (data.success && data.holdings && data.holdings.length > 0) {
                        currentHoldings = [...currentHoldings, ...data.holdings];
                        await saveHoldings();
                        renderHoldings();
                        imageResultEl.className = 'image-result';
                        imageResultEl.innerHTML = `✓ 识别成功！共找到 ${data.holdings.length} 条持仓：<br>` + 
                            data.holdings.map(h => `${h.name} (${h.code})`).join('<br>');
                        showToast('识别成功，已添加到持仓列表');
                    } else {
                        imageResultEl.className = 'image-result error';
                        imageResultEl.textContent = '✗ 未能在图片中识别到持仓信息，请尝试手动输入或使用文件导入';
                    }
                } catch (err) {
                    imageResultEl.className = 'image-result error';
                    imageResultEl.textContent = '✗ 识别失败，请尝试手动输入';
                }
            };
            reader.readAsDataURL(file);
        });

        const templateLink = document.getElementById('download-template');
        templateLink.addEventListener('click', (e) => {
            e.preventDefault();
            const csv = 'name,code,amount,cost,current_price,sector\n上海瀚讯,300762.SZ,1000,25.50,,商业航天\n贵州茅台,600519.SH,500,1800.00,,白酒\n';
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

        document.getElementById('btn-refresh-prices').addEventListener('click', async () => {
            showToast('正在刷新价格...');
            for (let i = 0; i < currentHoldings.length; i++) {
                const h = currentHoldings[i];
                if (h.code) {
                    const data = await fetchJSON(`/api/price?code=${encodeURIComponent(h.code)}`);
                    if (data.success && data.price) {
                        currentHoldings[i].current_price = data.price;
                    }
                }
            }
            await saveHoldings();
            renderHoldings();
            showToast('价格已刷新');
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
