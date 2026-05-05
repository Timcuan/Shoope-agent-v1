const STATS_URL = 'http://localhost:8000/api/stats';
const ANALYTICS_URL = 'http://localhost:8000/api/analytics';
const LOGS_URL = 'http://localhost:8000/api/logs';
let apiKey = sessionStorage.getItem('api_key') || '';

async function fetchAll() {
    if (!apiKey) return;
    
    try {
        const headers = { 'X-API-Key': apiKey };
        const [statsRes, analyticsRes, logsRes] = await Promise.all([
            fetch(STATS_URL, { headers }),
            fetch(ANALYTICS_URL, { headers }),
            fetch(LOGS_URL, { headers })
        ]);

        if (statsRes.status === 401 || analyticsRes.status === 401) {
            showLoginError("API Key tidak valid");
            showLoginOverlay();
            return;
        }

        const stats = await statsRes.json();
        const analytics = await analyticsRes.json();
        const logs = await logsRes.json();

        hideLoginOverlay();
        updateDashboard(stats, analytics, logs);
    } catch (error) {
        console.error('Failed to fetch data:', error);
        document.querySelector('.status-indicator').innerHTML = '<span class="pulse" style="background:var(--danger); animation:none;"></span> Terputus';
        document.querySelector('.status-indicator').style.color = 'var(--danger)';
    }
}

function updateDashboard(stats, analytics, logs) {
    // Header Status
    document.querySelector('.status-indicator').innerHTML = '<span class="pulse"></span> Sistem Aktif';
    document.querySelector('.status-indicator').style.color = 'var(--success)';
    document.getElementById('last-update').innerText = new Date().toLocaleTimeString('id-ID');

    // Financial KPIs
    animateCurrency("kpi-revenue", analytics.revenue);
    const growthEl = document.getElementById('kpi-growth');
    growthEl.innerText = `${analytics.growth_revenue >= 0 ? '+' : ''}${analytics.growth_revenue.toFixed(1)}% vs Bln Lalu`;
    growthEl.className = `kpi-trend ${analytics.growth_revenue >= 0 ? 'positive' : 'negative'}`;

    animateValue("kpi-orders", analytics.order_count);
    animateValue("kpi-tasks", stats.tasks);
    
    const taskStatusEl = document.getElementById('kpi-tasks-status');
    if (stats.tasks > 0) {
        taskStatusEl.innerText = "Butuh Perhatian";
        taskStatusEl.className = "kpi-trend negative";
    } else {
        taskStatusEl.innerText = "Semua Selesai";
        taskStatusEl.className = "kpi-trend positive";
    }

    // Dispute Analytics
    document.getElementById('kpi-dispute-rate').innerText = `${analytics.dispute_rate.toFixed(2)}%`;
    document.getElementById('kpi-dispute-count').innerText = analytics.dispute_count;
    
    const healthEl = document.getElementById('kpi-health-status');
    if (analytics.dispute_rate > 2) {
        healthEl.innerText = "KRITIS";
        healthEl.className = "status-warn";
    } else {
        healthEl.innerText = "NORMAL";
        healthEl.className = "status-ok";
    }

    // Decision Bars
    const totalDecisions = stats.decisions.low + stats.decisions.medium + stats.decisions.high;
    if (totalDecisions > 0) {
        document.getElementById('bar-low').style.width = `${(stats.decisions.low / totalDecisions) * 100}%`;
        document.getElementById('bar-medium').style.width = `${(stats.decisions.medium / totalDecisions) * 100}%`;
        document.getElementById('bar-high').style.width = `${(stats.decisions.high / totalDecisions) * 100}%`;
    }

    animateValue("val-low", stats.decisions.low);
    animateValue("val-medium", stats.decisions.medium);
    animateValue("val-high", stats.decisions.high);

    // Activity Feed
    const feedEl = document.getElementById('activity-feed');
    if (logs && logs.length > 0) {
        feedEl.innerHTML = logs.map(l => {
            const time = new Date(l.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
            let icon = '●';
            if (l.severity === 'error') icon = '🚨';
            if (l.severity === 'warning') icon = '⚠️';
            
            return `
                <div class="activity-item ${l.severity}">
                    <span class="a-time">${time}</span>
                    <span class="a-icon">${icon}</span>
                    <span class="a-msg">${l.message}</span>
                </div>
            `;
        }).join('');
    }
}

function animateCurrency(id, end) {
    const obj = document.getElementById(id);
    const currentStr = obj.innerText.replace(/[^0-9]/g, '');
    const current = parseInt(currentStr) || 0;
    if (current === end) return;

    let startTimestamp = null;
    const duration = 1000;

    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const value = Math.floor(progress * (end - current) + current);
        obj.innerText = `Rp ${value.toLocaleString('id-ID')}`;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function animateValue(id, end) {
    const obj = document.getElementById(id);
    const current = parseInt(obj.innerText.replace(/,/g, '')) || 0;
    if (current === end) return;
    
    let startTimestamp = null;
    const duration = 1000;

    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const value = Math.floor(progress * (end - current) + current);
        obj.innerText = value.toLocaleString('id-ID');
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Login Handling
function showLoginOverlay() {
    document.getElementById('login-overlay').style.display = 'flex';
    document.getElementById('app-container').style.display = 'none';
}

function hideLoginOverlay() {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('app-container').style.display = 'block';
}

function showLoginError(msg) {
    document.getElementById('login-error').innerText = msg;
}

document.getElementById('login-btn').addEventListener('click', () => {
    const key = document.getElementById('api-key-input').value;
    if (key) {
        apiKey = key;
        sessionStorage.setItem('api_key', key);
        fetchAll();
    } else {
        showLoginError("API Key tidak boleh kosong");
    }
});

document.getElementById('api-key-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        document.getElementById('login-btn').click();
    }
});

// Initial boot
if (!apiKey) {
    showLoginOverlay();
} else {
    fetchAll();
}

// Poll every 10 seconds
setInterval(fetchAll, 10000);
