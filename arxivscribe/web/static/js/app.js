// ArxivScribe frontend
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// --- Theme ---
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);
$('#btn-theme').addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
});

// --- Tabs ---
$$('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        $$('.tab').forEach(t => t.classList.remove('active'));
        $$('.tab-content').forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        $(`#tab-${tab.dataset.tab}`).classList.add('active');
        if (tab.dataset.tab === 'bookmarks') loadBookmarks();
        if (tab.dataset.tab === 'digests') loadDigests();
    });
});

// --- Status ---
function showStatus(msg, type = 'info') {
    const bar = $('#status-bar');
    bar.textContent = msg;
    bar.className = `status-bar ${type}`;
    bar.classList.remove('hidden');
    if (type !== 'error') setTimeout(() => bar.classList.add('hidden'), 5000);
}

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
    for (const keyword of kw.split(',').map(k => k.trim()).filter(Boolean)) {
        try { await api(`/api/subscribe?keyword=${encodeURIComponent(keyword)}`, { method: 'POST' }); addTag(keyword); }
        catch (e) { showStatus(`Failed: ${e.message}`, 'error'); }
    }
    input.value = '';
    updateStats();
});
$('#keyword-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#btn-subscribe').click(); });

function addTag(keyword) {
    const tags = $('#keyword-tags');
    if (tags.querySelector(`[data-keyword="${keyword}"]`)) return;
    const span = document.createElement('span');
    span.className = 'tag';
    span.innerHTML = `${esc(keyword)} <button class="tag-remove" data-keyword="${esc(keyword)}">&times;</button>`;
    span.querySelector('.tag-remove').addEventListener('click', () => removeTag(keyword, span));
    tags.appendChild(span);
}

async function removeTag(keyword, el) {
    try { await api(`/api/subscribe?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE' }); el.remove(); updateStats(); }
    catch (e) { showStatus(`Failed: ${e.message}`, 'error'); }
}
$$('.tag-remove').forEach(btn => btn.addEventListener('click', () => removeTag(btn.dataset.keyword, btn.parentElement)));

// --- Fetch ---
async function fetchPapers(useKeywords = true) {
    const btn = useKeywords ? $('#btn-fetch') : $('#btn-fetch-all');
    const orig = btn.textContent;
    btn.disabled = true; btn.textContent = 'Fetching...';
    $('#loading').classList.remove('hidden');
    try {
        const data = await api(`/api/fetch?summarize=true&use_keywords=${useKeywords}`, { method: 'POST' });
        showStatus(`Fetched ${data.fetched} papers, ${data.new} new`, 'success');
        await loadPapers();
    } catch (e) { showStatus(`Fetch failed: ${e.message}`, 'error'); }
    finally { btn.disabled = false; btn.textContent = orig; $('#loading').classList.add('hidden'); }
}
$('#btn-fetch').addEventListener('click', () => fetchPapers(true));
$('#btn-fetch-all').addEventListener('click', () => fetchPapers(false));

// ==========================================
// PAGINATION + FILTER STATE
// ==========================================
let currentPage = 1;
let currentSort = 'date';
let perPage = 20;
let filterTimer = null;

function getFilters() {
    return {
        sort: $('#sort-select').value,
        keyword: $('#filter-input').value.trim() || undefined,
        date_from: $('#date-from').value || undefined,
        date_to: $('#date-to').value || undefined,
        category: $('#cat-filter').value || undefined,
        per_page: parseInt($('#per-page-select').value) || 20,
    };
}

async function loadPapers(page = 1) {
    currentPage = page;
    const f = getFilters();
    perPage = f.per_page;

    const params = new URLSearchParams({ page, per_page: perPage, sort: f.sort });
    if (f.keyword) params.set('keyword', f.keyword);
    if (f.date_from) params.set('date_from', f.date_from);
    if (f.date_to) params.set('date_to', f.date_to);
    if (f.category) params.set('category', f.category);

    try {
        const data = await api(`/api/papers?${params}`);
        renderPapers(data.papers, '#papers');
        $('#paper-count').textContent = data.total;
        $('#empty-state').classList.toggle('hidden', data.papers.length > 0);
        updatePagination(data);
    } catch (e) { console.error('Load failed:', e); }
}

function updatePagination(data) {
    $('#pg-prev').disabled = !data.has_prev;
    $('#pg-next').disabled = !data.has_next;
    $('#pg-info').textContent = `Page ${data.page} of ${data.total_pages} (${data.total} papers)`;
}

$('#pg-prev').addEventListener('click', () => { if (currentPage > 1) loadPapers(currentPage - 1); });
$('#pg-next').addEventListener('click', () => loadPapers(currentPage + 1));

// Filter change handlers
$('#sort-select').addEventListener('change', () => loadPapers(1));
$('#date-from').addEventListener('change', () => loadPapers(1));
$('#date-to').addEventListener('change', () => loadPapers(1));
$('#cat-filter').addEventListener('change', () => loadPapers(1));
$('#per-page-select').addEventListener('change', () => loadPapers(1));
$('#filter-input').addEventListener('input', () => {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => loadPapers(1), 300);
});

// ==========================================
// RENDER PAPERS
// ==========================================
function renderPapers(papers, container, opts = {}) {
    const el = $(container);
    if (!papers.length) { el.innerHTML = '<div class="empty-state"><p>No papers found</p></div>'; return; }

    const kwTags = $$('#keyword-tags .tag');
    const keywords = Array.from(kwTags).map(t => t.textContent.replace('\u00d7', '').trim().toLowerCase());

    el.innerHTML = papers.map(p => {
        const authors = Array.isArray(p.authors) ? p.authors : (p.authors || '').split(',');
        const categories = Array.isArray(p.categories) ? p.categories : (p.categories || '').split(',');
        const matchedKw = Array.isArray(p.matched_keywords) ? p.matched_keywords : (p.matched_keywords || '').split(',');
        const title = highlightKeywords(esc(p.title || ''), keywords);
        const summary = p.summary ? highlightKeywords(esc(p.summary), keywords) : '';
        const date = (p.published || '').substring(0, 10);
        const simScore = opts.showSimilarity && p.similarity_score
            ? ` <span class="cat-tag">${(p.similarity_score * 100).toFixed(0)}% match</span>` : '';

        return `
        <article class="paper-card" data-id="${esc(p.id)}">
            <div class="paper-vote">
                <button class="vote-btn vote-up" data-id="${esc(p.id)}" data-type="up">&#9650;</button>
                <span class="vote-score">${p.score || 0}</span>
                <button class="vote-btn vote-down" data-id="${esc(p.id)}" data-type="down">&#9660;</button>
            </div>
            <div class="paper-content">
                <h3 class="paper-title"><a href="${p.url || ''}" target="_blank">${title}</a></h3>
                <p class="paper-authors">${esc(authors.slice(0,4).join(', '))}${authors.length > 4 ? ` +${authors.length-4}` : ''}</p>
                ${summary ? `<p class="paper-summary">${summary}</p>` : ''}
                <div class="paper-meta">
                    ${categories.filter(Boolean).map(c => `<span class="cat-tag">${esc(c)}</span>`).join('')}
                    ${matchedKw.filter(Boolean).map(k => `<span class="kw-tag">${esc(k)}</span>`).join('')}
                    <span class="paper-date">${date}</span>
                    ${p.pdf_url ? `<a href="${p.pdf_url}" target="_blank" class="pdf-link">PDF</a>` : ''}
                    ${simScore}
                </div>
                <div class="paper-actions">
                    <button class="action-btn bookmark-btn" data-id="${esc(p.id)}">&#9733; Save</button>
                    <button class="action-btn similar-btn" data-id="${esc(p.id)}">&#8776; Similar</button>
                </div>
            </div>
        </article>`;
    }).join('');

    el.querySelectorAll('.vote-btn').forEach(btn => btn.addEventListener('click', () => vote(btn.dataset.id, btn.dataset.type, btn)));
    el.querySelectorAll('.bookmark-btn').forEach(btn => btn.addEventListener('click', () => bookmark(btn.dataset.id, btn)));
    el.querySelectorAll('.similar-btn').forEach(btn => btn.addEventListener('click', () => showSimilar(btn.dataset.id)));
}

function highlightKeywords(text, keywords) {
    if (!keywords.length) return text;
    const pattern = keywords.filter(Boolean).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    if (!pattern) return text;
    return text.replace(new RegExp(`(${pattern})`, 'gi'), '<mark class="kw-highlight">$1</mark>');
}

function esc(str) { const d = document.createElement('div'); d.textContent = str || ''; return d.innerHTML; }

// --- Voting ---
async function vote(paperId, type, btn) {
    try {
        const data = await api(`/api/vote/${encodeURIComponent(paperId)}?vote_type=${type}`, { method: 'POST' });
        btn.closest('.paper-card').querySelector('.vote-score').textContent = data.score;
    } catch (e) { console.error('Vote failed:', e); }
}

// --- Bookmarks ---
async function bookmark(paperId, btn) {
    try {
        await api(`/api/bookmark/${encodeURIComponent(paperId)}`, { method: 'POST' });
        btn.classList.add('bookmarked'); btn.innerHTML = '&#9733; Saved';
        showStatus('Paper bookmarked', 'success');
    } catch (e) { showStatus(`Bookmark failed: ${e.message}`, 'error'); }
}

async function loadBookmarks(collection = null) {
    try {
        const params = collection ? `?collection=${encodeURIComponent(collection)}` : '';
        const data = await api(`/api/bookmarks${params}`);
        renderPapers(data.bookmarks, '#bookmarks-list');
        const bar = $('#collections-bar');
        bar.innerHTML = (data.collections || []).map(c =>
            `<button class="collection-btn${c.name === collection ? ' active' : ''}" data-collection="${esc(c.name)}">${esc(c.name)} (${c.count})</button>`
        ).join('');
        bar.querySelectorAll('.collection-btn').forEach(btn =>
            btn.addEventListener('click', () => loadBookmarks(btn.dataset.collection)));
    } catch (e) { console.error('Bookmarks failed:', e); }
}

// --- Similar ---
async function showSimilar(paperId) {
    const modal = $('#similar-modal');
    modal.classList.remove('hidden');
    $('#similar-papers').innerHTML = '<div class="loading"><div class="spinner"></div><span>Finding similar papers...</span></div>';
    try {
        const data = await api(`/api/similar/${encodeURIComponent(paperId)}`);
        const papers = data.papers.map(item => ({ ...item.paper, similarity_score: item.score }));
        renderPapers(papers, '#similar-papers', { showSimilarity: true });
    } catch (e) { $('#similar-papers').innerHTML = '<div class="empty-state"><p>Could not find similar papers</p></div>'; }
}
$('#modal-close').addEventListener('click', () => $('#similar-modal').classList.add('hidden'));
$('#similar-modal').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden'); });

// --- Search ---
$('#btn-search').addEventListener('click', doSearch);
$('#search-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
async function doSearch() {
    const q = $('#search-input').value.trim();
    if (!q) return;
    const btn = $('#btn-search');
    btn.disabled = true; btn.textContent = 'Searching...';
    try {
        const data = await api(`/api/search?q=${encodeURIComponent(q)}&count=15`);
        renderPapers(data.papers, '#search-results');
        showStatus(`Found ${data.count} papers`, 'success');
    } catch (e) { showStatus(`Search failed: ${e.message}`, 'error'); }
    finally { btn.disabled = false; btn.textContent = 'Search'; }
}

// --- Export ---
$('#btn-export').addEventListener('click', () => {
    const fmt = $('#export-format').value;
    window.open(`/api/export?fmt=${fmt}&limit=200`, '_blank');
});
const bmExportBtn = $('#btn-export-bookmarks');
if (bmExportBtn) bmExportBtn.addEventListener('click', () => window.open('/api/export?fmt=bibtex&collection=Reading%20List', '_blank'));

// ==========================================
// EMAIL DIGESTS
// ==========================================
$('#btn-create-digest').addEventListener('click', async () => {
    const email = $('#digest-email').value.trim();
    if (!email) { showStatus('Please enter an email', 'error'); return; }

    const params = new URLSearchParams({
        email,
        keywords: $('#digest-keywords').value.trim(),
        categories: $('#digest-categories').value.trim(),
        schedule: $('#digest-schedule').value,
        send_hour: $('#digest-hour').value,
    });

    try {
        await api(`/api/digests?${params}`, { method: 'POST' });
        showStatus('Digest created!', 'success');
        loadDigests();
    } catch (e) { showStatus(`Failed: ${e.message}`, 'error'); }
});

$('#btn-test-digest').addEventListener('click', async () => {
    const email = $('#digest-email').value.trim();
    if (!email) { showStatus('Enter email first', 'error'); return; }
    const btn = $('#btn-test-digest');
    btn.disabled = true; btn.textContent = 'Sending...';
    try {
        const data = await api(`/api/digests/test?email=${encodeURIComponent(email)}`, { method: 'POST' });
        showStatus(data.message, data.status === 'ok' ? 'success' : 'error');
    } catch (e) { showStatus(`Failed: ${e.message}`, 'error'); }
    finally { btn.disabled = false; btn.textContent = 'Send Test Email'; }
});

async function loadDigests() {
    try {
        const data = await api('/api/digests');
        const list = $('#digest-list');
        if (!data.digests.length) {
            list.innerHTML = '<p class="text-muted">No digests configured yet.</p>';
            return;
        }
        list.innerHTML = data.digests.map(d => `
            <div class="digest-card">
                <div>
                    <div class="digest-info">${esc(d.target)} &mdash; ${d.schedule} at ${d.send_hour}:00 UTC</div>
                    <div class="digest-meta">
                        ${d.keywords ? `Keywords: ${esc(d.keywords)}` : 'All topics'}
                        ${d.categories ? ` | Categories: ${esc(d.categories)}` : ''}
                        ${d.last_sent ? ` | Last sent: ${d.last_sent.substring(0,16)}` : ' | Never sent'}
                    </div>
                </div>
                <div class="digest-actions">
                    <button class="btn btn-secondary" onclick="toggleDigest(${d.id}, ${!d.enabled})">${d.enabled ? 'Pause' : 'Resume'}</button>
                    <button class="btn btn-secondary" style="color:var(--red)" onclick="deleteDigest(${d.id})">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (e) { console.error('Digests failed:', e); }
}

window.toggleDigest = async (id, enabled) => {
    await api(`/api/digests/${id}/toggle?enabled=${enabled}`, { method: 'POST' });
    loadDigests();
};

window.deleteDigest = async (id) => {
    if (!confirm('Delete this digest?')) return;
    await api(`/api/digests/${id}`, { method: 'DELETE' });
    loadDigests();
};

// --- Stats ---
async function updateStats() {
    try { const s = await api('/api/stats'); $('#stat-papers').textContent = s.total_papers; $('#stat-subs').textContent = s.total_subscriptions; }
    catch (e) {}
}

// --- Init ---
updateStats();
