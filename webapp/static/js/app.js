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
                if (pageName === 'trades') loadTrades();
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
        let totalPnl = 0;

        currentHoldings.forEach(h => {
            const amount = parseFloat(h.amount) || 0;
            const current = parseFloat(h.current_price) || 0;
            const value = parseFloat(h.value) || (amount * current);
            const cost = parseFloat(h.cost) || 0;
            const pnl = parseFloat(h.pnl) || 0;

            totalAmount += amount;
            totalValue += value;
            totalCost += amount * cost;
            totalPnl += pnl;
        });

        const totalProfit = totalValue - totalCost;

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

            const currentPrice = parseFloat(h.current_price) || 0;
            const stopLoss = parseFloat(h.stop_loss) || 0;
            let stopLossClass = '';
            let stopLossHint = '';
            if (stopLoss > 0 && currentPrice > 0) {
                const distance = ((currentPrice - stopLoss) / currentPrice * 100).toFixed(2);
                if (currentPrice <= stopLoss) {
                    stopLossClass = 'stop-loss-triggered';
                    stopLossHint = '⚠️ 已触发止损';
                } else if (distance <= 3) {
                    stopLossClass = 'stop-loss-warning';
                    stopLossHint = `距止损 ${distance}%`;
                } else {
                    stopLossHint = `距止损 ${distance}%`;
                }
            }

            return `
            <div class="holding-card">
                <div class="holding-card-header">
                    <div class="holding-card-title">
                        <div class="holding-card-name">${escapeHtml(h.name)}</div>
                        <div class="holding-card-meta">
                            <span class="holding-card-code">${escapeHtml(h.code || '')}</span>
                            ${h.sector ? `<span class="holding-card-sector-tag">${escapeHtml(h.sector)}</span>` : ''}
                        </div>
                    </div>
                    <div class="holding-card-price">
                        <div class="holding-card-current-price ${pnlClass}">¥${parseFloat(h.current_price || 0).toFixed(2)}</div>
                        <div class="holding-card-change-rate ${pnlClass}">
                            ${pnlSign}${pnl_rate}%
                        </div>
                        ${h.price_source ? `<div class="holding-card-price-source">${escapeHtml(h.price_source)}</div>` : ''}
                    </div>
                </div>
                ${h.buy_reason ? `<div class="holding-card-reason"><span class="reason-label">买入逻辑：</span>${escapeHtml(h.buy_reason)}</div>` : ''}
                <div class="holding-card-body">
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">持仓数量</div>
                        <div class="holding-card-item-value">${(parseFloat(h.amount) || 0).toLocaleString()}</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">仓位%</div>
                        <div class="holding-card-item-value">${(parseFloat(h.position) || 0).toFixed(2)}%</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">买入价</div>
                        <div class="holding-card-item-value">¥${parseFloat(h.cost || 0).toFixed(3)}</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">浮动盈亏</div>
                        <div class="holding-card-item-value ${pnlClass}">${pnlSign}¥${parseFloat(pnl).toLocaleString()}</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">盈亏比例</div>
                        <div class="holding-card-item-value ${pnlClass}">${pnlSign}${pnl_rate}%</div>
                    </div>
                    <div class="holding-card-item">
                        <div class="holding-card-item-label">止损价</div>
                        <div class="holding-card-item-value ${stopLossClass} stop-loss-value" data-index="${i}" title="点击修改止损价">
                            ¥${stopLoss.toFixed(2)}
                            <span class="stop-loss-edit-icon">✏️</span>
                            ${stopLossHint ? `<div class="stop-loss-hint">${stopLossHint}</div>` : ''}
                        </div>
                    </div>
                </div>
                <div class="holding-card-actions">
                    <button class="holding-card-btn-profit" data-index="${i}">止盈</button>
                    <button class="holding-card-btn-loss" data-index="${i}">止损</button>
                    <button class="holding-card-btn-edit" data-index="${i}">编辑</button>
                    <button class="holding-card-btn-delete" data-index="${i}">删除</button>
                </div>
            </div>
        `}).join('');

        listEl.querySelectorAll('.holding-card-btn-delete').forEach(btn => {
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

        listEl.querySelectorAll('.holding-card-btn-edit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                const h = currentHoldings[idx];
                document.getElementById('holding-name').value = h.name || '';
                document.getElementById('holding-code').value = h.code || '';
                document.getElementById('holding-amount').value = h.amount || '';
                document.getElementById('holding-available').value = h.available || '';
                document.getElementById('holding-position').value = h.position || '';
                document.getElementById('holding-current').value = h.current_price || '';
                document.getElementById('holding-cost').value = h.cost || '';
                document.getElementById('holding-pnl').value = h.pnl || '';
                document.getElementById('holding-stop-loss').value = h.stop_loss || '';
                document.getElementById('holding-sector').value = h.sector || '';
                document.getElementById('holding-buy-reason').value = h.buy_reason || '';
                document.getElementById('holding-date').value = h.buy_date || '';
                currentHoldings.splice(idx, 1);
                saveHoldings();
                renderHoldings();
                document.getElementById('holding-name').focus();
                showToast('编辑模式：修改后点击添加即可更新');
            });
        });

        listEl.querySelectorAll('.stop-loss-value').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(el.dataset.index);
                openStopLossModal(idx);
            });
        });

        listEl.querySelectorAll('.holding-card-btn-profit').forEach(btn => {
            btn.addEventListener('click', (e) => openCloseModal(e, 'profit'));
        });

        listEl.querySelectorAll('.holding-card-btn-loss').forEach(btn => {
            btn.addEventListener('click', (e) => openCloseModal(e, 'loss'));
        });

        updateSummary();
    }

    // 弹框相关
    let modalCloseType = 'manual';
    let modalHoldingIdx = -1;
    let modalHolding = null;
    let slModalIdx = -1;

    function openStopLossModal(idx) {
        const h = currentHoldings[idx];
        if (!h) return;
        slModalIdx = idx;

        document.getElementById('sl-modal-stock-name').textContent = h.name;
        document.getElementById('sl-modal-stock-code').textContent = h.code || '';

        const currentPrice = parseFloat(h.current_price) || 0;
        const stopLoss = parseFloat(h.stop_loss) || 0;

        document.getElementById('sl-modal-price').value = stopLoss > 0 ? stopLoss.toFixed(2) : '';
        document.getElementById('sl-modal-current').textContent = '¥' + currentPrice.toFixed(2);
        updateStopLossPreview();

        document.getElementById('stop-loss-modal').classList.remove('hidden');
    }

    function closeStopLossModal() {
        document.getElementById('stop-loss-modal').classList.add('hidden');
        slModalIdx = -1;
    }

    window.closeStopLossModal = closeStopLossModal;

    function updateStopLossPreview() {
        const price = parseFloat(document.getElementById('sl-modal-price').value) || 0;
        const h = currentHoldings[slModalIdx];
        if (!h) return;
        const current = parseFloat(h.current_price) || 0;
        const distEl = document.getElementById('sl-modal-distance');
        if (price <= 0 || current <= 0) {
            distEl.textContent = '--';
            return;
        }
        const distance = ((current - price) / current * 100).toFixed(2);
        if (current <= price) {
            distEl.textContent = '已触发止损';
            distEl.style.color = 'var(--danger)';
        } else {
            distEl.textContent = distance + '%';
            distEl.style.color = '';
        }
    }

    async function confirmStopLoss() {
        if (slModalIdx < 0) return;
        const value = parseFloat(document.getElementById('sl-modal-price').value);
        if (isNaN(value) || value < 0) {
            showToast('请输入有效的止损价');
            return;
        }
        currentHoldings[slModalIdx].stop_loss = value;
        await saveHoldings();
        closeStopLossModal();
        renderHoldings();
        showToast('止损价已更新');
    }

    function openCloseModal(e, closeType) {
        const idx = parseInt(e.currentTarget.dataset.index);
        const h = currentHoldings[idx];
        if (!h) return;

        modalCloseType = closeType;
        modalHoldingIdx = idx;
        modalHolding = h;

        const typeText = closeType === 'profit' ? '止盈平仓' : '止损平仓';
        document.getElementById('modal-title').textContent = typeText;
        document.getElementById('modal-stock-name').textContent = h.name;
        document.getElementById('modal-stock-code').textContent = h.code || '';
        document.getElementById('modal-total-amount').textContent = h.amount || 0;

        // 尝试获取实时价格
        fetchRealtimePrice(h.code, (price) => {
            document.getElementById('modal-price').value = price.toFixed(2);
            updateModalPreview();
        }, () => {
            const defaultPrice = parseFloat(h.current_price) || 0;
            document.getElementById('modal-price').value = defaultPrice.toFixed(2);
            updateModalPreview();
        });

        document.getElementById('modal-amount').value = '';
        document.getElementById('modal-note').value = '';
        document.getElementById('close-modal').classList.remove('hidden');
    }

    async function fetchRealtimePrice(code, onSuccess, onFail) {
        try {
            const res = await fetch(`/api/price?code=${encodeURIComponent(code)}`);
            const data = await res.json();
            if (data.success && data.price > 0) {
                onSuccess(data.price);
            } else {
                onFail();
            }
        } catch (e) {
            onFail();
        }
    }

    function closeModal() {
        document.getElementById('close-modal').classList.add('hidden');
        modalHoldingIdx = -1;
        modalHolding = null;
    }

    // 暴露给 HTML onclick
    window.closeModal = closeModal;

    function updateModalPreview() {
        if (!modalHolding) return;

        const price = parseFloat(document.getElementById('modal-price').value) || 0;
        const totalAmount = parseFloat(modalHolding.amount) || 0;
        const sellAmount = parseFloat(document.getElementById('modal-amount').value) || totalAmount;
        const buyPrice = parseFloat(modalHolding.cost) || 0;

        if (price <= 0 || buyPrice <= 0) {
            document.getElementById('modal-preview-pnl').textContent = '¥--';
            document.getElementById('modal-preview-rate').textContent = '--%';
            return;
        }

        const actualSell = sellAmount > totalAmount ? totalAmount : sellAmount;
        const pnl = (price - buyPrice) * actualSell;
        const pnlRate = ((price - buyPrice) / buyPrice * 100);

        const pnlEl = document.getElementById('modal-preview-pnl');
        pnlEl.textContent = (pnl >= 0 ? '+' : '') + '¥' + pnl.toFixed(2);
        pnlEl.className = 'preview-pnl ' + (pnl >= 0 ? 'positive' : 'negative');

        document.getElementById('modal-preview-rate').textContent = (pnlRate >= 0 ? '+' : '') + pnlRate.toFixed(2) + '%';
    }

    async function confirmClose() {
        if (modalHoldingIdx < 0 || !modalHolding) return;

        const closePrice = parseFloat(document.getElementById('modal-price').value) || 0;
        if (closePrice <= 0) {
            showToast('卖出价格必须大于0');
            return;
        }

        const sellAmount = parseFloat(document.getElementById('modal-amount').value) || 0;
        const note = document.getElementById('modal-note').value.trim();

        const typeText = modalCloseType === 'profit' ? '止盈' : '止损';

        try {
            const res = await fetch('/api/holdings/close', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    index: modalHoldingIdx,
                    close_type: modalCloseType,
                    close_price: closePrice,
                    close_note: note,
                    amount: sellAmount
                })
            });
            const data = await res.json();
            if (data.success) {
                closeModal();
                currentHoldings = data.holdings;
                renderHoldings();
                const pnl = data.trade.pnl;
                const pnlStr = pnl >= 0 ? `+¥${pnl.toFixed(2)}` : `-¥${Math.abs(pnl).toFixed(2)}`;
                const amountText = data.is_full ? '全部' : `部分(${data.trade.amount}股)`;
                showToast(`${typeText}${amountText}卖出成功！盈亏：${pnlStr}`);
            } else {
                showToast('平仓失败：' + data.message);
            }
        } catch (err) {
            showToast('平仓失败：' + err.message);
        }
    }

    async function handleClose(e, closeType) {
        // 已改用弹框，此函数保留备用
        openCloseModal(e, closeType);
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
                showToast('请填写证券名称和代码');
                return;
            }

            const holding = {
                name: name,
                code: code,
                amount: parseFloat(document.getElementById('holding-amount').value) || 0,
                available: parseFloat(document.getElementById('holding-available').value) || 0,
                position: parseFloat(document.getElementById('holding-position').value) || 0,
                current_price: parseFloat(document.getElementById('holding-current').value) || 0,
                cost: parseFloat(document.getElementById('holding-cost').value) || 0,
                pnl: parseFloat(document.getElementById('holding-pnl').value) || 0,
                stop_loss: parseFloat(document.getElementById('holding-stop-loss').value) || 0,
                sector: document.getElementById('holding-sector').value.trim(),
                buy_reason: document.getElementById('holding-buy-reason').value.trim(),
                buy_date: document.getElementById('holding-date').value
            };

            currentHoldings.push(holding);
            await saveHoldings();
            renderHoldings();
            form.reset();
            document.getElementById('code-hint').textContent = '';
            document.getElementById('code-hint').className = 'field-hint';
            showToast('添加成功');
        });

        document.getElementById('btn-fetch-info').addEventListener('click', async () => {
            const codeInput = document.getElementById('holding-code');
            const nameInput = document.getElementById('holding-name');
            const priceInput = document.getElementById('holding-current');
            const sectorInput = document.getElementById('holding-sector');
            const hintEl = document.getElementById('code-hint');
            
            let code = codeInput.value.trim();
            if (!code) {
                showToast('请先输入证券代码');
                return;
            }

            hintEl.textContent = '正在识别...';
            hintEl.className = 'field-hint';
            
            const data = await fetchJSON(`/api/stock/info?code=${encodeURIComponent(code)}`);
            if (data.success) {
                codeInput.value = data.code;
                nameInput.value = data.name;
                priceInput.value = data.price ? data.price.toFixed(2) : '';
                sectorInput.value = data.industry || '';
                hintEl.textContent = `✓ 已识别：${data.name}`;
                hintEl.className = 'field-hint success';
                showToast(`识别成功！${data.name} - ¥${data.price}`);
            } else {
                hintEl.textContent = `✗ ${data.message}`;
                hintEl.className = 'field-hint error';
                showToast('识别失败：' + data.message);
            }
        });

        document.getElementById('btn-fetch-price').addEventListener('click', async () => {
            const code = document.getElementById('holding-code').value.trim();
            if (!code) {
                showToast('请先输入证券代码');
                return;
            }
            showToast('正在获取价格...');
            const data = await fetchJSON(`/api/price?code=${encodeURIComponent(code)}`);
            if (data.success && data.price) {
                document.getElementById('holding-current').value = data.price.toFixed(2);
                showToast(`获取成功：¥${data.price.toFixed(2)}`);
            } else {
                showToast('获取价格失败：' + data.message);
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
                        imageResultEl.className = 'image-result success';
                        let html = `✓ 识别成功！共找到 ${data.holdings.length} 条持仓：<br><br>`;
                        html += '<table style="width:100%;font-size:12px;border-collapse:collapse;">';
                        html += '<tr style="background:#f0f0f0;"><th style="padding:4px;text-align:left;">名称</th><th style="padding:4px;text-align:left;">代码</th><th style="padding:4px;text-align:right;">数量</th></tr>';
                        data.holdings.forEach(h => {
                            html += `<tr><td style="padding:4px;">${escapeHtml(h.name)}</td><td style="padding:4px;">${escapeHtml(h.code)}</td><td style="padding:4px;text-align:right;">${h.amount || 0}</td></tr>`;
                        });
                        html += '</table>';
                        if (data.raw_text) {
                            html += `<br><details style="margin-top:8px;font-size:11px;color:#666;"><summary>查看识别原文</summary><pre style="background:#f5f5f5;padding:8px;border-radius:4px;overflow:auto;max-height:150px;">${escapeHtml(data.raw_text)}</pre></details>`;
                        }
                        imageResultEl.innerHTML = html;
                        showToast(`识别成功！共 ${data.holdings.length} 条`);
                    } else {
                        imageResultEl.className = 'image-result error';
                        let html = '✗ ' + (data.message || '未能识别持仓信息');
                        if (data.raw_text) {
                            html += `<br><details style="margin-top:8px;font-size:11px;color:#666;"><summary>查看识别原文（用于调试）</summary><pre style="background:#f5f5f5;padding:8px;border-radius:4px;overflow:auto;max-height:200px;">${escapeHtml(data.raw_text)}</pre></details>`;
                        }
                        imageResultEl.innerHTML = html;
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
            const csv = 'name,code,amount,cost,current_price,stop_loss,sector,buy_reason\n上海瀚讯,300762.SZ,1000,25.50,,23.00,商业航天,突破平台放量\n贵州茅台,600519.SH,500,1800.00,,1650.00,白酒,业绩超预期\n';
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
            let successCount = 0;
            for (let i = 0; i < currentHoldings.length; i++) {
                const h = currentHoldings[i];
                if (h.code) {
                    const data = await fetchJSON(`/api/price?code=${encodeURIComponent(h.code)}`);
                    if (data.success && data.price) {
                        currentHoldings[i].current_price = data.price;
                        currentHoldings[i].price_source = data.source_name || '';
                        successCount++;
                    }
                }
            }
            await saveHoldings();
            renderHoldings();
            showToast(`价格已刷新 (${successCount}/${currentHoldings.length})`);
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

    function initCloseModal() {
        // 价格变化时更新预览
        document.getElementById('modal-price').addEventListener('input', updateModalPreview);
        // 数量变化时更新预览
        document.getElementById('modal-amount').addEventListener('input', updateModalPreview);
        // 全部按钮
        document.getElementById('modal-all-btn').addEventListener('click', () => {
            document.getElementById('modal-amount').value = document.getElementById('modal-total-amount').textContent;
            updateModalPreview();
        });
        // 确认按钮
        document.getElementById('modal-confirm-btn').addEventListener('click', confirmClose);
    }

    function initStopLossModal() {
        document.getElementById('sl-modal-price').addEventListener('input', updateStopLossPreview);
        document.getElementById('sl-modal-confirm-btn').addEventListener('click', confirmStopLoss);
    }

    async function init() {
        initNav();
        initHoldingForm();
        initFileUpload();
        initClearHoldings();
        initConfigForm();
        initRefreshButtons();
        initCloseModal();
        initStopLossModal();
        initTradesPage();

        await loadStatus();
        await loadDailyReview();
    }

    // ============ 交易记录 ============
    let currentTrades = [];

    async function loadTrades() {
        const listEl = document.getElementById('trades-list');
        listEl.innerHTML = '<p style="text-align:center;color:var(--text-light);padding:20px;">加载中...</p>';

        const [trades, stats] = await Promise.all([
            fetchJSON('/api/trades'),
            fetchJSON('/api/trades/stats')
        ]);

        currentTrades = trades;
        renderTradesStats(stats);
        renderTrades(trades);
    }

    function renderTradesStats(stats) {
        document.getElementById('trade-total').textContent = stats.total;
        document.getElementById('trade-winrate').textContent = stats.win_rate + '%';
        const totalPnlEl = document.getElementById('trade-total-pnl');
        totalPnlEl.textContent = (stats.total_pnl >= 0 ? '+' : '') + '¥' + stats.total_pnl.toLocaleString();
        totalPnlEl.className = 'summary-value ' + (stats.total_pnl >= 0 ? 'positive' : 'negative');
        const avgPnlEl = document.getElementById('trade-avg-pnl');
        avgPnlEl.textContent = (stats.avg_pnl >= 0 ? '+' : '') + '¥' + stats.avg_pnl.toLocaleString();
        avgPnlEl.className = 'summary-value ' + (stats.avg_pnl >= 0 ? 'positive' : 'negative');
        document.getElementById('trade-avg-days').textContent = stats.avg_hold_days;
        document.getElementById('trade-best-worst').textContent =
            '+' + stats.best_trade + ' / ' + stats.worst_trade;
    }

    function renderTrades(trades) {
        const listEl = document.getElementById('trades-list');

        if (!trades || trades.length === 0) {
            listEl.innerHTML = '<div class="empty-state"><p>暂无交易记录</p><p style="font-size:12px;margin-top:8px;">在持仓管理中点击"止盈"或"止损"会自动记录到这里</p></div>';
            return;
        }

        listEl.innerHTML = trades.map(t => {
            const pnl = parseFloat(t.pnl) || 0;
            const pnlClass = pnl >= 0 ? 'positive' : 'negative';
            const pnlSign = pnl >= 0 ? '+' : '';
            const typeText = t.close_type === 'profit' ? '止盈' : t.close_type === 'loss' ? '止损' : '手动';
            const typeClass = t.close_type === 'profit' ? 'trade-type-profit' : t.close_type === 'loss' ? 'trade-type-loss' : 'trade-type-manual';

            return `
            <div class="trade-card">
                <div class="trade-card-header">
                    <div class="trade-card-title">
                        <span class="trade-type-badge ${typeClass}">${typeText}</span>
                        <span class="trade-card-name">${escapeHtml(t.name)}</span>
                        <span class="trade-card-code">${escapeHtml(t.code || '')}</span>
                        ${t.sector ? `<span class="trade-card-sector">${escapeHtml(t.sector)}</span>` : ''}
                    </div>
                    <div class="trade-card-pnl ${pnlClass}">
                        <div class="trade-card-pnl-value">${pnlSign}¥${pnl.toLocaleString()}</div>
                        <div class="trade-card-pnl-rate">${pnlSign}${t.pnl_rate}%</div>
                    </div>
                </div>
                ${t.buy_reason ? `<div class="trade-card-reason"><span class="reason-label">买入逻辑：</span>${escapeHtml(t.buy_reason)}</div>` : ''}
                <div class="trade-card-body">
                    <div class="trade-card-item"><span class="label">买入价</span><span class="value">¥${parseFloat(t.buy_price || 0).toFixed(3)}</span></div>
                    <div class="trade-card-item"><span class="label">卖出价</span><span class="value">¥${parseFloat(t.close_price || 0).toFixed(2)}</span></div>
                    <div class="trade-card-item"><span class="label">数量</span><span class="value">${parseFloat(t.amount || 0).toLocaleString()}</span></div>
                    <div class="trade-card-item"><span class="label">买入日</span><span class="value">${t.buy_date || '-'}</span></div>
                    <div class="trade-card-item"><span class="label">卖出日</span><span class="value">${t.close_date || '-'}</span></div>
                    <div class="trade-card-item"><span class="label">持仓天数</span><span class="value">${t.hold_days}天</span></div>
                </div>
                ${t.close_note ? `<div class="trade-card-note">📝 ${escapeHtml(t.close_note)}</div>` : ''}
            </div>
            `;
        }).join('');
    }

    function initTradesPage() {
        document.getElementById('btn-clear-trades').addEventListener('click', async () => {
            if (confirm('确定要清空所有交易记录吗？此操作不可撤销。')) {
                await fetchJSON('/api/trades', { method: 'DELETE' });
                await loadTrades();
                showToast('交易记录已清空');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
