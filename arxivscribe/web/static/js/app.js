// ArxivScribe frontend
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// --- Theme ---
const themeBtn = $('#btn-theme');
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
themeBtn.textContent = savedTheme === 'dark' ? '🌙' : '☀️';

themeBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    themeBtn.textContent = next === 'dark' ? '🌙' : '☀️';
});

// --- Status ---
function showStatus(msg, type = 'info') {
    const bar = $('#status-bar');
    bar.textContent = msg;
    bar.className = `status-bar ${type}`;
    bar.classList.remove('hidden');
    if (type !== 'error') setTimeout(() => bar.classList.add('hidden'), 5000);
}

// --- API helpers ---
async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

// --- Subscribe ---
$('#btn-subscribe').addEventListener('click', async () => {
    const input = $('#keyword-input');
    const kw = input.value.trim();
    if (!kw) return;

    // Support comma-separated
    const keywords = kw.split(',').map(k => k.trim()).filter(Boolean);
    for (const keyword of keywords) {
        try {
            await api(`/api/subscribe?keyword=${encodeURIComponent(keyword)}`, { method: 'POST' });
            addTag(keyword);
        } catch (e) {
            showStatus(`Failed to subscribe: ${e.message}`, 'error');
        }
    }
    input.value = '';
    updateStats();
});

$('#keyword-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('#btn-subscribe').click();
});

function addTag(keyword) {
    const tags = $('#keyword-tags');
    // Check if already exists
    if (tags.querySelector(`[data-keyword="${keyword}"]`)) return;

    const span = document.createElement('span');
    span.className = 'tag';
    span.innerHTML = `${keyword} <button class="tag-remove" data-keyword="${keyword}">×</button>`;
    span.querySelector('.tag-remove').addEventListener('click', () => removeTag(keyword, span));
    tags.appendChild(span);
}

async function removeTag(keyword, el) {
    try {
        await api(`/api/subscribe?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE' });
        el.remove();
        updateStats();
    } catch (e) {
        showStatus(`Failed to unsubscribe: ${e.message}`, 'error');
    }
}

// Bind existing tag remove buttons
$$('.tag-remove').forEach(btn => {
    btn.addEventListener('click', () => removeTag(btn.dataset.keyword, btn.parentElement));
});

// --- Fetch papers ---
async function fetchPapers(useKeywords = true) {
    const btn = useKeywords ? $('#btn-fetch') : $('#btn-fetch-all');
    btn.disabled = true;
    btn.textContent = '⏳ Fetching...';
    $('#loading').classList.remove('hidden');

    try {
        const data = await api(`/api/fetch?summarize=true&use_keywords=${useKeywords}`, { method: 'POST' });
        showStatus(`Fetched ${data.fetched} papers, ${data.new} new`, 'success');
        await loadPapers();
    } catch (e) {
        showStatus(`Fetch failed: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = useKeywords ? '📡 Fetch Papers' : '📡 Fetch All (no filter)';
        $('#loading').classList.add('hidden');
    }
}

$('#btn-fetch').addEventListener('click', () => fetchPapers(true));
$('#btn-fetch-all').addEventListener('click', () => fetchPapers(false));

// --- Load papers ---
let currentSort = 'date';

async function loadPapers(sort = currentSort, keyword = null) {
    try {
        const params = new URLSearchParams({ sort, limit: 100 });
        if (keyword) params.set('keyword', keyword);
        const data = await api(`/api/papers?${params}`);
        renderPapers(data.papers);
        $('#paper-count').textContent = data.total;
        $('#empty-state').classList.toggle('hidden', data.papers.length > 0);
    } catch (e) {
        console.error('Failed to load papers:', e);
    }
}

function renderPapers(papers) {
    const container = $('#papers');
    container.innerHTML = papers.map(p => `
        <article class="paper-card" data-id="${p.id}">
            <div class="paper-vote">
                <button class="vote-btn vote-up" data-id="${p.id}" data-type="up">▲</button>
                <span class="vote-score">${p.score || 0}</span>
                <button class="vote-btn vote-down" data-id="${p.id}" data-type="down">▼</button>
            </div>
            <div class="paper-content">
                <h3 class="paper-title">
                    <a href="${p.url}" target="_blank" rel="noopener">${esc(p.title)}</a>
                </h3>
                <p class="paper-authors">${esc((p.authors || []).join(', '))}</p>
                ${p.summary ? `<p class="paper-summary">${esc(p.summary)}</p>` : ''}
                <div class="paper-meta">
                    ${(p.categories || []).map(c => `<span class="cat-tag">${esc(c)}</span>`).join('')}
                    ${(p.matched_keywords || []).filter(Boolean).map(k => `<span class="kw-tag">${esc(k)}</span>`).join('')}
                    <span class="paper-date">${(p.published || '').substring(0, 10)}</span>
                    ${p.pdf_url ? `<a href="${p.pdf_url}" target="_blank" class="pdf-link">📄 PDF</a>` : ''}
                </div>
            </div>
        </article>
    `).join('');

    // Bind vote buttons
    container.querySelectorAll('.vote-btn').forEach(btn => {
        btn.addEventListener('click', () => vote(btn.dataset.id, btn.dataset.type, btn));
    });
}

function esc(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
}

// --- Voting ---
async function vote(paperId, type, btn) {
    try {
        const data = await api(`/api/vote/${encodeURIComponent(paperId)}?vote_type=${type}`, { method: 'POST' });
        const card = btn.closest('.paper-card');
        card.querySelector('.vote-score').textContent = data.score;
    } catch (e) {
        console.error('Vote failed:', e);
    }
}

// --- Sort ---
$$('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.sort-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentSort = btn.dataset.sort;
        loadPapers(currentSort);
    });
});

// --- Search ---
$('#btn-search').addEventListener('click', async () => {
    const q = $('#search-input').value.trim();
    if (!q) return;

    $('#btn-search').disabled = true;
    $('#btn-search').textContent = '⏳';
    $('#loading').classList.remove('hidden');

    try {
        const data = await api(`/api/search?q=${encodeURIComponent(q)}&count=10`);
        renderPapers(data.papers);
        $('#paper-count').textContent = data.count;
        $('#empty-state').classList.add('hidden');
        showStatus(`Found ${data.count} papers for "${q}"`, 'success');
    } catch (e) {
        showStatus(`Search failed: ${e.message}`, 'error');
    } finally {
        $('#btn-search').disabled = false;
        $('#btn-search').textContent = '🔍';
        $('#loading').classList.add('hidden');
    }
});

$('#search-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('#btn-search').click();
});

// --- Stats ---
async function updateStats() {
    try {
        const s = await api('/api/stats');
        $('#stat-papers').textContent = s.total_papers;
        $('#stat-subs').textContent = s.total_subscriptions;
    } catch (e) {}
}

// Init
updateStats();
