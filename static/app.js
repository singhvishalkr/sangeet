/* ═══════════════════════════════════════════════════════════════
   Sangeet — Production Dashboard
   ═══════════════════════════════════════════════════════════════ */

const AUTH = '';
let ws = null;
let activity = null;
let tab = 'home';
let status = null;
let playing = false;
let paused = false;
let vol = 50;
let prevVol = 50;
let seekDragging = false;
let allPlaylists = [];
let activeFilter = null;
let searchIndex = [];
let shuffleOn = true;
let repeatMode = 'no';
let liked = false;
let npPanelOpen = false;
let plDetailId = null;
let sleepInterval = null;
let _prevTrackTitle = null;

let interpPos = 0;
let interpDur = 0;
let interpLastSync = 0;
let interpRaf = null;

const $ = id => document.getElementById(id);
const hdr = () => AUTH ? { 'X-Auth-Token': AUTH } : {};
const jhdr = () => ({ 'Content-Type': 'application/json', ...hdr() });
const pretty = s => (s || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

function fmtTime(sec) {
  if (!sec || sec < 0) return '--:--';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function fmtCountdown(sec) {
  if (sec <= 0) return '0:00';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}` : `${m}:${s.toString().padStart(2, '0')}`;
}

/* ─── TABS ─── */
function switchTab(t) {
  tab = t;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const pg = $('page-' + t);
  const btn = document.querySelector(`.nav-btn[data-tab="${t}"]`);
  if (pg) pg.classList.add('active');
  if (btn) btn.classList.add('active');
  if (t === 'queue') loadQueue();
  if (t === 'playlists') loadPlaylists();
  if (t === 'discover') loadDiscover();
  if (t === 'schedule') loadSchedule();
  if (t === 'analytics') loadAnalytics();
  if (t === 'home') loadRecentlyPlayed();
  closeSidebar();
}

function toggleSidebar() { $('sidebar').classList.toggle('open'); }
function closeSidebar() { if (innerWidth <= 960) $('sidebar').classList.remove('open'); }

/* ─── WEBSOCKET ─── */
let wsRetryDelay = 1000;
function connectWS() {
  const p = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${p}//${location.host}/ws`);
  ws.onopen = () => { setConn('ok'); wsRetryDelay = 1000; };
  ws.onmessage = e => {
    try { const d = JSON.parse(e.data); status = d; render(d); } catch {}
  };
  ws.onclose = () => {
    setConn('err');
    setTimeout(connectWS, wsRetryDelay);
    wsRetryDelay = Math.min(wsRetryDelay * 1.5, 15000);
  };
  ws.onerror = () => ws.close();
}

function setConn(state) {
  const dots = document.querySelectorAll('.conn-dot');
  dots.forEach(d => { d.className = 'conn-dot ' + state; });
  const txt = $('connText');
  if (txt) txt.textContent = state === 'ok' ? 'Connected' : 'Reconnecting...';
  const liveDot = $('liveDot');
  if (liveDot) {
    liveDot.className = state === 'ok' ? 'dot' : 'dot off';
  }
  const liveLabel = $('liveLabel');
  if (liveLabel) liveLabel.textContent = state === 'ok' ? 'Live' : 'Offline';
}

/* ─── RENDER ─── */
function render(d) {
  const c = d.current || {};
  const dec = d.decision || {};

  const playlistName = c.playlist_name || pretty(c.playlist_id || '');
  const trackTitle = c.track_title;
  playing = !!c.playlist_id;
  paused = !!c.is_paused;

  $('npName').textContent = playlistName || 'Nothing Playing';
  $('npTrack').textContent = trackTitle || '';
  $('npSlot').textContent = dec.slot_name || pretty(dec.slot_id || '');
  $('npTags').innerHTML = (c.tags || []).map(t => `<span class="tag">${t}</span>`).join('');

  const badge = $('npBadge');
  if (c.playlist_pos >= 0 && c.playlist_count > 0) {
    badge.textContent = `Track ${c.playlist_pos + 1} of ${c.playlist_count}`;
    badge.style.display = '';
  } else {
    badge.style.display = 'none';
  }

  const liveDot = $('liveDot');
  if (liveDot) {
    if (!playing) liveDot.className = 'dot off';
    else if (paused) liveDot.className = 'dot paused';
    else liveDot.className = 'dot';
  }

  $('reasons').innerHTML = (dec.reasons || []).map(r => `<li>${r}</li>`).join('') || '<li>No decision data yet</li>';

  // Transport info
  const tName = $('tName');
  const displayName = trackTitle || playlistName || '--';
  tName.textContent = displayName;
  updateMarquee(tName, displayName);

  $('tSlot').textContent = dec.slot_name || pretty(dec.slot_id || '');

  const pos = c.track_position || 0;
  const dur = c.track_duration || 0;

  interpPos = pos;
  interpDur = dur;
  interpLastSync = performance.now();
  if (!interpRaf && playing && !paused && dur > 0) startInterpolation();
  if (!playing || paused || dur <= 0) {
    stopInterpolation();
    updateProgressUI(pos, dur);
  }

  const v = c.volume ?? 50;
  vol = v;
  syncVolumeUI(v);
  updatePlayIcon();

  const wave = $('tWave');
  wave.className = 't-wave' + (!playing ? ' off' : paused ? ' paused' : '');

  const transport = $('transport');
  transport.classList.toggle('glow', playing && !paused);

  const mode = d.room_mode || 'normal';
  $('modeLabel').textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
  document.querySelectorAll('#roomChips .chip').forEach(ch =>
    ch.classList.toggle('active', ch.dataset.mode === mode)
  );

  // Now Playing Panel sync
  renderNpPanel(c, dec);

  // Detect track change → refresh lyrics automatically
  if (trackTitle && trackTitle !== _prevTrackTitle) {
    _onTrackChanged(trackTitle);
  } else if (!_prevTrackTitle && trackTitle) {
    _prevTrackTitle = trackTitle;
  }

  // Keep lyrics highlight loop alive when synced lyrics are loaded
  if (lyricsVisible && syncedLyricsData && !lyricsHighlightRaf) {
    startLyricsHighlight();
  }

  // Sleep timer sync
  renderSleepTimer(d.sleep_timer);
}

function updateProgressUI(pos, dur) {
  if (dur > 0) {
    $('tTime').textContent = `${fmtTime(pos)} / ${fmtTime(dur)}`;
    if (!seekDragging) {
      const pct = Math.min((pos / dur) * 100, 100);
      $('progressBar').style.width = pct + '%';
      $('progressInput').value = Math.round((pos / dur) * 1000);
    }
  } else {
    $('tTime').textContent = '';
    $('progressBar').style.width = '0';
    $('progressInput').value = 0;
  }
  const npPos = $('npPanelPos');
  const npDur = $('npPanelDur');
  const npBar = $('npPanelBarFill');
  if (npPos) npPos.textContent = fmtTime(pos);
  if (npDur) npDur.textContent = fmtTime(dur);
  if (npBar) npBar.style.width = dur > 0 ? Math.min((pos / dur) * 100, 100) + '%' : '0';
}

function startInterpolation() {
  if (interpRaf) return;
  function tick() {
    if (!playing || paused || interpDur <= 0) { interpRaf = null; return; }
    const elapsed = (performance.now() - interpLastSync) / 1000;
    const currentPos = Math.min(interpPos + elapsed, interpDur);
    updateProgressUI(currentPos, interpDur);
    interpRaf = requestAnimationFrame(tick);
  }
  interpRaf = requestAnimationFrame(tick);
}

function stopInterpolation() {
  if (interpRaf) { cancelAnimationFrame(interpRaf); interpRaf = null; }
}

function updateMarquee(el, text) {
  if (!el) return;
  el.classList.remove('scrolling');
  if (el.scrollWidth > el.parentElement.offsetWidth + 10) {
    el.textContent = text + '     ' + text + '     ';
    el.classList.add('scrolling');
  }
}

function renderNpPanel(c, dec) {
  const trackTitle = c.track_title;
  const playlistName = c.playlist_name || pretty(c.playlist_id || '');
  $('npPanelTrack').textContent = trackTitle || playlistName || '--';
  $('npPanelPlaylist').textContent = playlistName || '--';
  $('npPanelPath').textContent = trackTitle ? `Playing from: ${playlistName}` : '';
  $('npPanelTags').innerHTML = (c.tags || []).map(t => `<span class="tag">${t}</span>`).join('');

  const npPlayIcon = $('npPlayIcon');
  if (npPlayIcon) {
    npPlayIcon.innerHTML = (playing && !paused)
      ? '<path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z"/>'
      : '<path d="M8 5v14l11-7z"/>';
  }

  // Gradient shift based on tags
  const bg = $('npPanelBg');
  if (bg && c.tags) {
    const tagStr = (c.tags || []).join('');
    let hue1 = 142, hue2 = 220;
    for (let i = 0; i < tagStr.length; i++) {
      hue1 = (hue1 + tagStr.charCodeAt(i) * 7) % 360;
      hue2 = (hue2 + tagStr.charCodeAt(i) * 13) % 360;
    }
    bg.style.background = `radial-gradient(ellipse at 30% 20%,hsla(${hue1},70%,40%,.25),transparent 60%),radial-gradient(ellipse at 70% 80%,hsla(${hue2},60%,40%,.2),transparent 60%),linear-gradient(180deg,#0a0a12,#06060a)`;
  }

  // Sync shuffle/repeat indicators in panel
  const npShuffle = $('npShuffleBtn');
  if (npShuffle) npShuffle.className = 't-btn t-shuffle np-ctrl' + (shuffleOn ? ' on' : '');
  const npRepeat = $('npRepeatBtn');
  if (npRepeat) npRepeat.className = 't-btn t-repeat np-ctrl' + (repeatMode === 'inf' ? ' on' : repeatMode === 'force' ? ' one' : '');
}

function renderSleepTimer(timer) {
  if (!timer) return;
  const pill = $('sleepPill');
  const active = $('sleepActive');
  const remaining = $('sleepRemaining');

  if (timer.active) {
    pill.style.display = '';
    active.style.display = '';
    remaining.textContent = `Stops in ${fmtCountdown(timer.remaining_seconds)}`;
    if (!sleepInterval) {
      sleepInterval = setInterval(() => {
        if (status?.sleep_timer?.active) {
          const r = status.sleep_timer.remaining_seconds;
          if (r > 0) {
            status.sleep_timer.remaining_seconds = r - 1;
            remaining.textContent = `Stops in ${fmtCountdown(r - 1)}`;
          }
        }
      }, 1000);
    }
  } else {
    pill.style.display = 'none';
    active.style.display = 'none';
    if (sleepInterval) { clearInterval(sleepInterval); sleepInterval = null; }
  }
}

function updatePlayIcon() {
  const playPath = '<path d="M8 5v14l11-7z"/>';
  const pausePath = '<path d="M6 5h4v14H6V5zm8 0h4v14h-4V5z"/>';
  const icon = (playing && !paused) ? pausePath : playPath;
  $('tPlayIcon').innerHTML = icon;
}

function syncVolumeUI(v) {
  const slider = $('tVol');
  if (slider) slider.value = v;
  const num = $('tVolNum');
  if (num) num.textContent = v;
  updateVolumeIcon(v);
}

function updateVolumeIcon(v) {
  const icon = $('tVolIcon');
  if (!icon) return;
  if (v === 0) {
    icon.innerHTML = '<path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51A8.8 8.8 0 0021 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.99 8.99 0 003.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>';
  } else if (v < 50) {
    icon.innerHTML = '<path d="M3 10v4h4l5 5V5L7 10H3zm13.5 2c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>';
  } else {
    icon.innerHTML = '<path d="M3 10v4h4l5 5V5L7 10H3zm13.5 2c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>';
  }
}

/* ─── API HELPERS ─── */
async function api(url, opts = {}) {
  try {
    const r = await fetch(url, { headers: hdr(), ...opts });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    toast(e.message || 'Request failed', 'error');
    return null;
  }
}

async function apiPost(url, body = null) {
  const opts = { method: 'POST', headers: jhdr() };
  if (body) opts.body = JSON.stringify(body);
  else opts.headers = hdr();
  try {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    toast(e.message || 'Request failed', 'error');
    return null;
  }
}

async function apiDelete(url) {
  try {
    const r = await fetch(url, { method: 'DELETE', headers: hdr() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    toast(e.message || 'Request failed', 'error');
    return null;
  }
}

async function refresh() {
  const d = await api('/status');
  if (d) { status = d; render(d); }
  loadTimeline();
  loadRecentlyPlayed();
}

/* ─── TIMELINE ─── */
async function loadTimeline() {
  const items = await api('/decisions?limit=8');
  const el = $('timeline');
  if (!items?.length) {
    el.innerHTML = '<div class="empty">No activity yet<br><span class="empty-cta" onclick="switchTab(\'playlists\')">Browse playlists</span></div>';
    return;
  }
  el.innerHTML = items.map(d => {
    const t = new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const what = d.action === 'play' ? pretty(d.playlist_id) : 'Stopped';
    const why = humanizeReason(d.reason);
    const cands = (d.candidates || []).slice(0, 3).map(c => pretty(c.playlist_id)).join(', ');
    return `<div class="tl-item">
      <div class="tl-time">${t}</div>
      <div>
        <div class="tl-what">${what}</div>
        <div class="tl-why">${why}</div>
        ${cands ? `<div class="tl-scores">Also considered: ${cands}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

function humanizeReason(reason) {
  const map = {
    'slot_resolution': 'Matched your schedule',
    'manual_override_play': 'You chose this playlist',
    'manual_override_stop': 'You paused playback',
    'no_active_slot': 'No scheduled slot right now',
    'no_eligible_playlist': 'No matching playlist found',
    'startup': 'System started',
    'override': 'Manual override applied',
    'override_cleared': 'Resumed automatic schedule',
    'quiet_hours': 'Quiet hours active',
    'api_reconcile': 'Refreshed by dashboard',
    'mpv_recovery': 'Player recovered automatically',
    'tick': 'Routine check',
    'sleep_timer': 'Sleep timer stopped playback',
  };
  return map[reason] || pretty(reason);
}

/* ─── RECENTLY PLAYED ─── */
async function loadRecentlyPlayed() {
  const d = await api('/recently-played?limit=5');
  const card = $('recentlyPlayedCard');
  const el = $('recentlyPlayedList');
  if (!d?.length) { card.style.display = 'none'; return; }
  card.style.display = '';
  el.innerHTML = d.map(p => `
    <div class="recent-item" onclick="quickOverride('${p.id}')">
      <div class="recent-name">${pretty(p.name)}</div>
      <div class="recent-tags">${(p.tags || []).slice(0, 3).join(', ')}</div>
    </div>
  `).join('');
}

/* ─── QUEUE ─── */
async function loadQueue() {
  const d = await api('/queue');
  const el = $('queueList');
  const sub = $('queueSub');
  if (!d?.tracks?.length) {
    el.innerHTML = '<div class="empty">No tracks in queue<br><span class="empty-cta" onclick="switchTab(\'playlists\')">Pick a playlist</span></div>';
    sub.textContent = 'Start playing a playlist to see tracks here';
    return;
  }
  const currentPos = status?.current?.playlist_pos ?? -1;
  sub.textContent = `Playing from: ${pretty(d.playlist_name || d.playlist_id)} \u2014 ${d.tracks.length} tracks`;
  el.innerHTML = d.tracks.map((t, i) => `
    <div class="q-item${i === currentPos ? ' current' : ''}">
      <div class="q-num">${i === currentPos ? '\u25B6' : i + 1}</div>
      <div class="q-name">${pretty(t.name)}</div>
      <div class="q-actions">
        <button class="q-like-btn" onclick="likeFeedback('${d.playlist_id}','${t.name}')" title="Like">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3z"/></svg>
        </button>
      </div>
    </div>`).join('');
}

/* ─── PLAYLISTS ─── */
async function loadPlaylists() {
  const d = await api('/playlists');
  if (!d?.length) {
    $('playlistGrid').innerHTML = '<div class="empty">No playlists configured<br><span class="empty-cta">Check your config file</span></div>';
    return;
  }
  allPlaylists = d;
  buildPlaylistFilters(d);
  renderPlaylists(d);
  buildSearchIndex(d);
}

function buildPlaylistFilters(playlists) {
  const tags = new Set();
  playlists.forEach(p => (p.tags || []).forEach(t => tags.add(t)));
  const el = $('playlistFilters');
  el.innerHTML = '<button class="filter-chip active" onclick="filterPlaylists(null, this)">All</button>' +
    [...tags].sort().map(t =>
      `<button class="filter-chip" onclick="filterPlaylists('${t}', this)">${t}</button>`
    ).join('');
}

function filterPlaylists(tag, btn) {
  activeFilter = tag;
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const filtered = tag ? allPlaylists.filter(p => (p.tags || []).includes(tag)) : allPlaylists;
  renderPlaylists(filtered);
}

function renderPlaylists(list) {
  const currentId = status?.current?.playlist_id;
  $('playlistGrid').innerHTML = list.map(p => `
    <div class="pl-card${p.id === currentId ? ' active' : ''}" onclick="openPlDetail('${p.id}')">
      <div class="pl-name">${pretty(p.name)}</div>
      <div class="pl-meta">${p.track_count} tracks${p.shuffle ? ' \u00B7 Shuffle' : ''}</div>
      <div class="pl-tags">${(p.tags || []).map(t => `<span class="pl-tag">${t}</span>`).join('')}</div>
      <button class="pl-btn" onclick="event.stopPropagation();quickOverride('${p.id}')">Play Now</button>
    </div>`).join('');
}

/* ─── PLAYLIST DETAIL VIEW ─── */
async function openPlDetail(id) {
  plDetailId = id;
  const modal = $('plDetailModal');
  const playlist = allPlaylists.find(p => p.id === id);
  if (!playlist) return;

  $('plDetailName').textContent = pretty(playlist.name);
  $('plDetailMeta').textContent = `${playlist.track_count} tracks${playlist.shuffle ? ' \u00B7 Shuffle on' : ''} \u00B7 Volume: ${playlist.volume_start}\u2192${playlist.volume_target}`;
  $('plDetailTags').innerHTML = (playlist.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
  $('plDetailTracks').innerHTML = '<div class="empty"><span class="spinner"></span> Loading tracks...</div>';
  $('plDetailHealth').innerHTML = '';

  modal.classList.add('open');

  const [, health] = await Promise.all([
    api(`/queue`),
    api(`/playlist-health/${id}`),
  ]);

  if (health) {
    const score = health.overall_score ?? 0;
    const color = score >= 80 ? 'var(--green)' : score >= 50 ? 'var(--amber)' : 'var(--red)';
    $('plDetailHealth').innerHTML = `
      <div class="health-label">Health Score: <strong style="color:${color}">${score}%</strong></div>
      <div class="health-bar"><div class="health-fill" style="width:${score}%;background:${color}"></div></div>`;
  }

  const tracks = await api(`/queue`);
  if (tracks?.tracks?.length && tracks.playlist_id === id) {
    $('plDetailTracks').innerHTML = tracks.tracks.map((t, i) => `
      <div class="pl-detail-track">
        <div class="track-num">${i + 1}</div>
        <div class="track-name">${pretty(t.name)}</div>
      </div>`).join('');
  } else {
    $('plDetailTracks').innerHTML = `<div class="empty">Play this playlist to see its tracks</div>`;
  }
}

function closePlDetail() {
  $('plDetailModal').classList.remove('open');
  plDetailId = null;
}

function plDetailPlay() {
  if (plDetailId) {
    quickOverride(plDetailId);
    closePlDetail();
  }
}

/* ─── SCHEDULE ─── */
async function loadSchedule() {
  const d = await api('/schedule');
  const el = $('schedList');
  const day = $('schedDay');
  if (!d?.slots) { el.innerHTML = '<div class="empty">No schedule configured</div>'; return; }
  day.textContent = `Today is ${d.day.charAt(0).toUpperCase() + d.day.slice(1)}`;
  const today = d.slots.filter(s => s.is_today);
  el.innerHTML = today.length ? today.map(s => `
    <div class="sched-card ${s.is_active ? 'on' : ''}">
      <div class="sched-time">${s.start} \u2013 ${s.end}</div>
      <div><div class="sched-name">${s.name}</div><div class="sched-days">${s.weekdays.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(', ')}</div></div>
      <span class="sched-badge ${s.is_active ? 'on' : ''}">${s.is_active ? '\u25CF Now' : 'Later'}</span>
    </div>`).join('') : '<div class="empty">No slots scheduled for today</div>';
}

/* ─── ANALYTICS ─── */
async function loadAnalytics() {
  const [lis, hlth] = await Promise.all([
    api('/analytics/listening?days=7'),
    api('/analytics/health'),
  ]);
  const el = $('statsGrid');
  let h = '';
  if (lis) {
    h += `<div class="stat"><div class="stat-num c-green">${lis.total_sessions}</div><div class="stat-lbl">Sessions this week</div></div>`;
    h += `<div class="stat"><div class="stat-num c-blue">${(lis.playlists || []).length}</div><div class="stat-lbl">Unique playlists</div></div>`;
    h += `<div class="stat"><div class="stat-num c-purple">${lis.override_count || 0}</div><div class="stat-lbl">Manual overrides</div></div>`;
    buildSessionsChart(lis);
    buildTopPlaylists(lis);
  }
  if (hlth) {
    h += `<div class="stat"><div class="stat-num c-amber">${hlth.mpv_restarts || 0}</div><div class="stat-lbl">Player restarts</div></div>`;
    h += `<div class="stat"><div class="stat-num c-green">${hlth.config_reloads || 0}</div><div class="stat-lbl">Config reloads</div></div>`;
    h += `<div class="stat"><div class="stat-num">${(hlth.recent_errors || []).length}</div><div class="stat-lbl">Recent errors</div></div>`;
  }
  el.innerHTML = h || '<div class="empty">No data yet \u2014 check back after a few days of listening</div>';
}

function buildSessionsChart(lis) {
  const card = $('chartCard');
  const el = $('sessionsChart');
  const daily = lis.daily_sessions;
  if (!daily || !daily.length) { card.style.display = 'none'; return; }
  card.style.display = '';
  const max = Math.max(...daily.map(d => d.count), 1);
  el.innerHTML = daily.map(d => {
    const pct = Math.round((d.count / max) * 100);
    const dayLabel = new Date(d.date).toLocaleDateString([], { weekday: 'short' });
    return `<div class="bar-col">
      <div class="bar-value">${d.count}</div>
      <div class="bar-fill" style="height:${pct}%"></div>
      <div class="bar-label">${dayLabel}</div>
    </div>`;
  }).join('');
}

function buildTopPlaylists(lis) {
  const card = $('topPlaylistsCard');
  const el = $('topPlaylists');
  const playlists = lis.playlists;
  if (!playlists || !playlists.length) { card.style.display = 'none'; return; }
  card.style.display = '';
  const max = Math.max(...playlists.map(p => p.count), 1);
  el.innerHTML = playlists.slice(0, 8).map(p => {
    const pct = Math.round((p.count / max) * 100);
    return `<div class="h-bar-row">
      <div class="h-bar-name" title="${pretty(p.playlist_id)}">${pretty(p.playlist_id)}</div>
      <div class="h-bar-track"><div class="h-bar-fill" style="width:${pct}%"></div></div>
      <div class="h-bar-count">${p.count}</div>
    </div>`;
  }).join('');
}

/* ─── QUICK ACTIONS ─── */
function buildQuickActions() {
  const grid = $('quickActions');
  if (!grid) return;
  grid.innerHTML = `
    <button class="action-btn go" onclick="smartPlay()">
      <span class="action-icon">\u25B6\uFE0F</span><span>Smart Play</span>
    </button>
    <button class="action-btn go" onclick="clearOverride()">
      <span class="action-icon">\u{1F504}</span><span>Resume Schedule</span>
    </button>
    <button class="action-btn warn" onclick="pauseFor(60)">
      <span class="action-icon">\u23F8\uFE0F</span><span>Pause 1 Hour</span>
    </button>
    <button class="action-btn warn" onclick="pauseFor(120)">
      <span class="action-icon">\u23F8\uFE0F</span><span>Pause 2 Hours</span>
    </button>
  `;
}

/* ─── CONTROLS ─── */
async function quickOverride(id) {
  const r = await apiPost('/override', { playlist_id: id, ttl_minutes: 90 });
  if (r) { toast(`Now playing: ${pretty(id)}`); refresh(); }
}

async function smartPlay() {
  const r = await apiPost('/smart-play');
  if (r) { toast('Smart play started'); refresh(); }
}

async function pauseFor(min) {
  const r = await apiPost('/override', { stop_playback: true, ttl_minutes: min });
  if (r) { toast(`Paused for ${min} minutes`); refresh(); }
}

async function clearOverride() {
  const r = await fetch('/override', { method: 'DELETE', headers: hdr() });
  if (r.ok) { toast('Resumed automatic schedule'); refresh(); }
}

async function skipTrack() {
  await apiPost('/skip');
  toast('Skipped to next track');
}

async function previousTrack() {
  await apiPost('/previous');
  toast('Previous track');
}

function togglePlayPause() {
  if (!playing) {
    smartPlay();
    return;
  }
  if (paused) {
    apiPost('/resume').then(d => {
      if (d) { status = d; render(d); }
      else refresh();
    });
  } else {
    apiPost('/pause').then(d => {
      if (d) { status = d; render(d); }
      else refresh();
    });
  }
}

function toggleMute() {
  if (vol > 0) {
    prevVol = vol;
    onVolumeChange(0);
  } else {
    onVolumeChange(prevVol || 60);
  }
}

let volTimer = null;
function onVolumeChange(v) {
  v = parseInt(v);
  vol = v;
  syncVolumeUI(v);
  clearTimeout(volTimer);
  volTimer = setTimeout(async () => {
    await apiPost('/volume', { volume: v });
  }, 120);
}

/* ─── SHUFFLE / REPEAT ─── */
async function toggleShuffle() {
  const r = await apiPost('/shuffle');
  if (r) {
    shuffleOn = r.shuffle;
    updateShuffleUI();
    toast(shuffleOn ? 'Shuffle on' : 'Shuffle off');
  }
}

async function toggleRepeat() {
  const r = await apiPost('/repeat');
  if (r) {
    repeatMode = r.repeat;
    updateRepeatUI();
    const labels = { 'no': 'Repeat off', 'inf': 'Repeat all', 'force': 'Repeat one' };
    toast(labels[repeatMode] || 'Repeat off');
  }
}

function updateShuffleUI() {
  const btns = document.querySelectorAll('.t-shuffle');
  btns.forEach(b => {
    b.classList.toggle('on', shuffleOn);
  });
}

function updateRepeatUI() {
  const btns = document.querySelectorAll('.t-repeat');
  btns.forEach(b => {
    b.className = b.className.replace(/ on| one/g, '');
    if (repeatMode === 'inf') b.classList.add('on');
    else if (repeatMode === 'force') b.classList.add('one');
  });
}

/* ─── LIKE / DISLIKE ─── */
async function likeCurrentTrack() {
  const c = status?.current;
  if (!c?.playlist_id) return;
  liked = !liked;
  updateLikeUI();
  await apiPost('/feedback/like', {
    signal: 'like',
    playlist_id: c.playlist_id,
    track_info: c.track_title || null,
  });
  toast(liked ? 'Liked!' : 'Like removed');
}

async function dislikeCurrentTrack() {
  const c = status?.current;
  if (!c?.playlist_id) return;
  await apiPost('/feedback/dislike', {
    signal: 'dislike',
    playlist_id: c.playlist_id,
    track_info: c.track_title || null,
  });
  toast('Feedback recorded');
  skipTrack();
}

async function likeFeedback(playlistId, trackName) {
  await apiPost('/feedback/like', {
    signal: 'like',
    playlist_id: playlistId,
    track_info: trackName,
  });
  toast('Liked!');
}

function updateLikeUI() {
  const btns = document.querySelectorAll('.t-like');
  btns.forEach(b => b.classList.toggle('liked', liked));
  const npBtn = $('npLikeBtn');
  if (npBtn) npBtn.classList.toggle('active', liked);
}

/* ─── NOW PLAYING PANEL + LYRICS (Spotify-style karaoke) ─── */
let lastLyricsTrack = null;
let syncedLyricsData = null;
let lyricsHighlightRaf = null;
let lastHighlightIdx = -1;
let lyricsVisible = false;
let _lyricTransitions = null;

function toggleNowPlayingPanel() {
  npPanelOpen = !npPanelOpen;
  $('npPanel').classList.toggle('open', npPanelOpen);
  if (npPanelOpen) {
    document.body.style.overflow = 'hidden';
    _autoLoadLyricsIfNeeded();
  } else {
    document.body.style.overflow = '';
    stopLyricsHighlight();
  }
}

function _autoLoadLyricsIfNeeded() {
  const trackTitle = status?.current?.track_title;
  if (!trackTitle) return;
  if (trackTitle !== lastLyricsTrack || !lyricsVisible) {
    _loadLyricsForTrack(trackTitle);
  } else if (syncedLyricsData) {
    startLyricsHighlight();
  }
}

function _onTrackChanged(newTitle) {
  _prevTrackTitle = newTitle;
  if (lyricsVisible) {
    _loadLyricsForTrack(newTitle);
  }
}

function _parseLRC(lrc) {
  if (!lrc) return null;
  const parsed = [];
  const re = /^\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)/;
  for (const line of lrc.split('\n')) {
    const m = line.match(re);
    if (m) {
      const secs = parseInt(m[1]) * 60 + parseInt(m[2]) + parseInt(m[3].padEnd(3, '0')) / 1000;
      const text = m[4].trim();
      if (text) parsed.push({ time: secs, text });
    }
  }
  return parsed.length > 0 ? parsed : null;
}

function _buildActivationTimes(data) {
  if (!data || data.length === 0) return [];
  const times = [];
  times.push(data[0].time);
  for (let i = 1; i < data.length; i++) {
    const prev = data[i - 1].time;
    const cur = data[i].time;
    const gap = cur - prev;
    if (gap > 3.0) {
      times.push(cur + 0.4);
    } else if (gap > 1.5) {
      times.push(cur + 0.2);
    } else {
      times.push(cur);
    }
  }
  return times;
}

function startLyricsHighlight() {
  if (lyricsHighlightRaf) return;
  if (!syncedLyricsData) return;
  function tick() {
    if (!syncedLyricsData || !lyricsVisible) { lyricsHighlightRaf = null; return; }
    let pos;
    if (paused || !playing) {
      pos = interpPos;
    } else {
      const elapsed = (performance.now() - interpLastSync) / 1000;
      pos = Math.min(interpPos + elapsed, interpDur);
    }
    _highlightLyricLine(pos);
    lyricsHighlightRaf = requestAnimationFrame(tick);
  }
  lyricsHighlightRaf = requestAnimationFrame(tick);
}

function stopLyricsHighlight() {
  if (lyricsHighlightRaf) { cancelAnimationFrame(lyricsHighlightRaf); lyricsHighlightRaf = null; }
  lastHighlightIdx = -1;
}

function _highlightLyricLine(posSec) {
  if (!syncedLyricsData || !_lyricTransitions) return;

  let activeIdx = -1;
  for (let i = _lyricTransitions.length - 1; i >= 0; i--) {
    if (posSec >= _lyricTransitions[i]) { activeIdx = i; break; }
  }

  if (activeIdx === lastHighlightIdx) return;

  if (lastHighlightIdx >= 0 && activeIdx < lastHighlightIdx) {
    const diff = syncedLyricsData[lastHighlightIdx].time - posSec;
    if (diff < 0.5) return;
  }

  lastHighlightIdx = activeIdx;

  const content = $('lyricsContent');
  if (!content) return;
  const lines = content.querySelectorAll('.lyrics-line');
  lines.forEach((el, i) => {
    el.classList.remove('active', 'past', 'upcoming', 'next-up');
    if (i === activeIdx) {
      el.classList.add('active');
    } else if (i < activeIdx) {
      el.classList.add('past');
    } else if (i === activeIdx + 1) {
      el.classList.add('next-up');
    } else {
      el.classList.add('upcoming');
    }
  });
  if (activeIdx >= 0 && lines[activeIdx]) {
    lines[activeIdx].scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function toggleLyrics() {
  const content = $('lyricsContent');
  const toggle = $('lyricsToggleBtn');
  if (lyricsVisible) {
    lyricsVisible = false;
    content.style.display = 'none';
    stopLyricsHighlight();
    if (toggle) toggle.querySelector('span').textContent = 'Show Lyrics';
  } else {
    lyricsVisible = true;
    content.style.display = 'block';
    if (toggle) toggle.querySelector('span').textContent = 'Hide Lyrics';
    const trackTitle = status?.current?.track_title;
    if (trackTitle && trackTitle !== lastLyricsTrack) {
      _loadLyricsForTrack(trackTitle);
    } else if (syncedLyricsData) {
      startLyricsHighlight();
    }
  }
}

async function fetchLyrics() { toggleLyrics(); }

async function _loadLyricsForTrack(trackTitle) {
  const content = $('lyricsContent');
  const toggle = $('lyricsToggleBtn');
  if (!content) return;

  if (!trackTitle) {
    content.innerHTML = '<div class="lyrics-not-found">No track playing</div>';
    content.style.display = 'block';
    lyricsVisible = true;
    syncedLyricsData = null;
    _lyricTransitions = null;
    stopLyricsHighlight();
    return;
  }

  syncedLyricsData = null;
  _lyricTransitions = null;
  stopLyricsHighlight();
  lastHighlightIdx = -1;
  lastLyricsTrack = trackTitle;
  lyricsVisible = true;
  content.style.display = 'block';
  if (toggle) toggle.querySelector('span').textContent = 'Hide Lyrics';

  content.innerHTML = '<div class="lyrics-loading"><span class="spinner"></span> Searching lyrics...</div>';

  const d = await api(`/lyrics?title=${encodeURIComponent(trackTitle)}`);

  if (lastLyricsTrack !== trackTitle) return;

  if (d?.lyrics) {
    syncedLyricsData = _parseLRC(d.synced);
    _lyricTransitions = syncedLyricsData ? _buildActivationTimes(syncedLyricsData) : null;
    const displayLines = syncedLyricsData
      ? syncedLyricsData.map(l => l.text)
      : d.lyrics.split('\n').filter(l => l.trim());

    const linesHtml = displayLines.map((line, i) =>
      `<div class="lyrics-line upcoming" data-line="${i}">${line || '&nbsp;'}</div>`
    ).join('');

    const footer = `<div class="lyrics-footer">`
      + (d.source ? `<span class="lyrics-source">via ${d.source}</span>` : '')
      + (syncedLyricsData ? `<span class="lyrics-synced-badge">Synced</span>` : '')
      + `</div>`;

    content.innerHTML = linesHtml + footer;

    if (syncedLyricsData) {
      startLyricsHighlight();
    }
  } else {
    const artistInfo = d?.artist ? ` by ${d.artist}` : '';
    content.innerHTML = `<div class="lyrics-not-found">No lyrics found for "${d?.song || trackTitle}"${artistInfo}<br><br>Searched: lrclib.net, Genius, lyrics.ovh</div>`;
  }
}

/* ─── SLEEP TIMER ─── */
async function setSleepTimer(min) {
  const r = await apiPost('/sleep-timer', { minutes: min });
  if (r?.ok) {
    toast(`Sleep timer: ${min} minutes`);
    refresh();
  }
}

async function clearSleepTimer() {
  const r = await apiDelete('/sleep-timer');
  if (r?.ok) {
    toast('Sleep timer cancelled');
    refresh();
  }
}

/* ─── SEEK ─── */
const progressInput = $('progressInput');
if (progressInput) {
  progressInput.addEventListener('mousedown', () => { seekDragging = true; });
  progressInput.addEventListener('touchstart', () => { seekDragging = true; });
  progressInput.addEventListener('input', () => {
    const dur = status?.current?.track_duration || 0;
    if (dur > 0) {
      const pct = progressInput.value / 1000;
      $('progressBar').style.width = (pct * 100) + '%';
      $('tTime').textContent = `${fmtTime(pct * dur)} / ${fmtTime(dur)}`;
    }
  });
  const doSeek = () => {
    seekDragging = false;
    const dur = status?.current?.track_duration || 0;
    if (dur > 0) {
      const pos = (progressInput.value / 1000) * dur;
      apiPost(`/seek?position=${pos.toFixed(1)}`);
    }
  };
  progressInput.addEventListener('change', doSeek);
  progressInput.addEventListener('mouseup', () => { if (seekDragging) doSeek(); });
  progressInput.addEventListener('touchend', () => { if (seekDragging) doSeek(); });
}

/* ─── ROOM ─── */
async function setRoom(mode) {
  const r = await apiPost(`/room?mode=${mode}`);
  if (r) {
    toast(`Room mode: ${mode.charAt(0).toUpperCase() + mode.slice(1)}`);
    document.querySelectorAll('#roomChips .chip').forEach(c =>
      c.classList.toggle('active', c.dataset.mode === mode)
    );
    $('modeLabel').textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    refresh();
  }
}

/* ─── MOOD ─── */
const EL = { 1: 'Very Low', 2: 'Low', 3: 'Balanced', 4: 'High', 5: 'Very High' };
const VL = { 1: 'Sad', 2: 'Melancholic', 3: 'Neutral', 4: 'Happy', 5: 'Joyful' };

function updateMoodLabel() {
  $('energyLbl').textContent = EL[$('energy').value];
  $('valenceLbl').textContent = VL[$('valence').value];
}

function pickActivity(el) {
  const a = el.dataset.activity;
  document.querySelectorAll('#activityChips .chip').forEach(c => c.classList.remove('active'));
  if (activity === a) { activity = null; } else { el.classList.add('active'); activity = a; }
}

async function submitMood() {
  const body = { energy: +$('energy').value, valence: +$('valence').value };
  if (activity) body.activity = activity;
  const r = await apiPost('/mood', body);
  if (r) { toast('Mood applied \u2014 playlist may adjust'); refresh(); }
}

/* ─── SEARCH ─── */
function buildSearchIndex(playlists) {
  searchIndex = [];
  (playlists || []).forEach(p => {
    searchIndex.push({ type: 'playlist', id: p.id, label: p.name || p.id, tags: p.tags || [] });
  });
}

const searchInput = $('sidebarSearch');
const searchResults = $('searchResults');
let searchFocusIdx = -1;

if (searchInput) {
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) { searchResults.classList.remove('open'); return; }
    const results = searchIndex.filter(item => {
      const haystack = (item.label + ' ' + item.tags.join(' ')).toLowerCase();
      return haystack.includes(q);
    }).slice(0, 10);
    if (!results.length) { searchResults.classList.remove('open'); return; }
    searchFocusIdx = -1;
    searchResults.innerHTML = results.map((r, i) =>
      `<div class="sr-item" data-idx="${i}" onclick="searchSelect(${i})">
        <span class="sr-type">${r.type}</span>
        <span class="sr-label">${pretty(r.label)}</span>
      </div>`
    ).join('');
    searchResults.classList.add('open');
    searchResults._data = results;
  });

  searchInput.addEventListener('keydown', e => {
    if (!searchResults.classList.contains('open')) return;
    const items = searchResults.querySelectorAll('.sr-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      searchFocusIdx = Math.min(searchFocusIdx + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle('focused', i === searchFocusIdx));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      searchFocusIdx = Math.max(searchFocusIdx - 1, 0);
      items.forEach((el, i) => el.classList.toggle('focused', i === searchFocusIdx));
    } else if (e.key === 'Enter' && searchFocusIdx >= 0) {
      e.preventDefault();
      searchSelect(searchFocusIdx);
    } else if (e.key === 'Escape') {
      searchResults.classList.remove('open');
      searchInput.blur();
    }
  });

  searchInput.addEventListener('blur', () => {
    setTimeout(() => searchResults.classList.remove('open'), 200);
  });
}

function searchSelect(idx) {
  const data = searchResults._data;
  if (!data || !data[idx]) return;
  const item = data[idx];
  searchResults.classList.remove('open');
  searchInput.value = '';
  if (item.type === 'playlist') {
    quickOverride(item.id);
  }
}

/* ─── DISCOVER ─── */
let discoverData = null;
let discoverPages = {};
const DISCOVER_PAGE_SIZE = 6;
let discoverSearchTimer = null;

async function loadDiscover() {
  const el = $('discoverContent');
  el.innerHTML = '<div class="empty"><span class="spinner"></span> Loading trending songs...</div>';
  const d = await api('/discover/trending');
  if (!d?.categories || !Object.keys(d.categories).length) {
    el.innerHTML = `<div class="empty">No trending data yet. Install yt-dlp for auto-discovery.<br><code style="font-size:12px;color:var(--tx3)">pip install yt-dlp</code><br><br><button class="discover-scan-btn" onclick="scanTrending()">Scan Now</button></div>`;
    return;
  }
  discoverData = d;
  for (const catId of Object.keys(d.categories)) {
    if (!(catId in discoverPages)) discoverPages[catId] = 0;
  }
  renderDiscover();
}

function renderDiscover() {
  const d = discoverData;
  if (!d) return;
  const el = $('discoverContent');
  let html = `<div class="discover-search-bar">
    <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
    <input type="text" id="discoverSearch" class="discover-search-input" placeholder="Search any song, artist, or keyword..." oninput="onDiscoverSearch(this.value)" autocomplete="off" spellcheck="false">
  </div>
  <div id="discoverSearchResults" style="display:none"></div>`;

  for (const [catId, cat] of Object.entries(d.categories)) {
    const songs = cat.songs || [];
    if (!songs.length) continue;
    const page = discoverPages[catId] || 0;
    const totalPages = Math.ceil(songs.length / DISCOVER_PAGE_SIZE);
    const start = page * DISCOVER_PAGE_SIZE;
    const pageSongs = songs.slice(start, start + DISCOVER_PAGE_SIZE);

    html += `<div class="discover-cat">
      <div class="discover-cat-header">
        <div>
          <div class="discover-cat-name">${cat.name}</div>
          <div class="discover-cat-meta">${songs.length} songs${cat.last_updated ? ' \u00B7 Updated ' + new Date(cat.last_updated).toLocaleString() : ''}</div>
        </div>
        <div class="discover-nav">
          <span class="discover-page-info">${page + 1} / ${totalPages}</span>
          <button class="discover-nav-btn${page <= 0 ? ' disabled' : ''}" onclick="discoverPageNav('${catId}', -1)" ${page <= 0 ? 'disabled' : ''} aria-label="Previous">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
          </button>
          <button class="discover-nav-btn${page >= totalPages - 1 ? ' disabled' : ''}" onclick="discoverPageNav('${catId}', 1)" ${page >= totalPages - 1 ? 'disabled' : ''} aria-label="Next">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </button>
        </div>
      </div>
      <div class="discover-songs">${renderDiscoverSongs(pageSongs)}</div>
    </div>`;
  }
  html += `<div style="text-align:center;margin-top:16px"><button class="discover-scan-btn" onclick="scanTrending()">Refresh Trending</button></div>`;
  if (d.last_scan) {
    html += `<p style="text-align:center;font-size:11px;color:var(--tx3);margin-top:8px">Last scan: ${new Date(d.last_scan).toLocaleString()}</p>`;
  }
  el.innerHTML = html;
}

function renderDiscoverSongs(songs) {
  return songs.map(song => {
    const views = song.view_count ? formatViews(song.view_count) : '';
    const dur = song.duration ? fmtTime(song.duration) : '';
    const safeUrl = encodeURIComponent(song.url || '');
    const safeTitle = (song.title || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    return `<div class="discover-song">
      <div class="discover-thumb" onclick="discoverPlayNow('${safeUrl}', this)" title="Play now">${song.thumbnail ? `<img src="${song.thumbnail}" alt="" loading="lazy">` : '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55C7.79 13 6 14.79 6 17s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>'}
        <div class="discover-play-overlay"><svg viewBox="0 0 24 24" width="28" height="28" fill="#fff"><path d="M8 5v14l11-7z"/></svg></div>
      </div>
      <div class="discover-info">
        <div class="discover-title" title="${safeTitle}">${song.title}</div>
        <div class="discover-channel">${song.channel || ''}${dur ? ' \u00B7 ' + dur : ''}</div>
        ${views ? `<div class="discover-views">${views} views</div>` : ''}
      </div>
      <div class="discover-actions">
        <button class="discover-action-btn discover-queue-btn" onclick="discoverAddToQueue('${safeUrl}', this)" title="Add to queue">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>
        </button>
        <button class="discover-action-btn discover-add-btn" onclick="showPlaylistPicker(this, '${safeUrl}')" title="Add to playlist">+ Add</button>
      </div>
    </div>`;
  }).join('');
}

async function discoverPlayNow(encodedUrl, el) {
  const url = decodeURIComponent(encodedUrl);
  const overlay = el.querySelector('.discover-play-overlay');
  if (overlay) overlay.innerHTML = '<span class="spinner" style="width:20px;height:20px"></span>';
  toast('Streaming...');
  const r = await apiPost(`/discover/play?url=${encodeURIComponent(url)}`);
  if (overlay) overlay.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" fill="#fff"><path d="M8 5v14l11-7z"/></svg>';
  if (r?.ok) {
    toast('Now playing');
  } else {
    toast(r?.error || 'Failed to play', 'error');
  }
}

async function discoverAddToQueue(encodedUrl, btn) {
  const url = decodeURIComponent(encodedUrl);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>';
  const r = await apiPost(`/discover/queue?url=${encodeURIComponent(url)}`);
  if (r?.ok) {
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="var(--green)"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
    toast('Added to queue');
  } else {
    toast(r?.error || 'Failed to queue', 'error');
  }
  setTimeout(() => {
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>';
    btn.disabled = false;
  }, 3000);
}

function discoverPageNav(catId, direction) {
  const cat = discoverData?.categories?.[catId];
  if (!cat) return;
  const totalPages = Math.ceil((cat.songs || []).length / DISCOVER_PAGE_SIZE);
  const current = discoverPages[catId] || 0;
  const next = current + direction;
  if (next < 0 || next >= totalPages) return;
  discoverPages[catId] = next;
  renderDiscover();
}

function formatViews(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toString();
}

function showPlaylistPicker(btn, encodedUrl) {
  const existing = document.querySelector('.playlist-picker-dropdown');
  if (existing) existing.remove();

  const playlists = allPlaylists.length ? allPlaylists : [];
  if (!playlists.length) {
    addTrending(btn, encodedUrl, null);
    return;
  }
  const dropdown = document.createElement('div');
  dropdown.className = 'playlist-picker-dropdown';
  dropdown.innerHTML = `<div class="picker-title">Add to playlist:</div>` +
    playlists.map(p => `<div class="picker-item" onclick="addTrending(this.closest('.discover-actions').querySelector('.discover-add-btn'), '${encodedUrl}', '${p.id}')">${pretty(p.name)}</div>`).join('');
  btn.closest('.discover-actions').appendChild(dropdown);
  setTimeout(() => {
    const close = (e) => { if (!dropdown.contains(e.target)) { dropdown.remove(); document.removeEventListener('click', close); } };
    document.addEventListener('click', close);
  }, 10);
}

async function addTrending(btn, encodedUrl, playlistId) {
  const picker = document.querySelector('.playlist-picker-dropdown');
  if (picker) picker.remove();

  const url = decodeURIComponent(encodedUrl);
  const playlists = allPlaylists.length ? allPlaylists : (await api('/playlists')) || [];
  if (!playlists.length) { toast('No playlists available', 'error'); return; }
  if (!playlistId) playlistId = playlists[0].id;

  const origText = btn.textContent;
  btn.innerHTML = '<span class="spinner" style="width:12px;height:12px;display:inline-block"></span> Saving...';
  btn.disabled = true;
  try {
    const r = await apiPost(`/discover/add-to-playlist?playlist_id=${encodeURIComponent(playlistId)}&url=${encodeURIComponent(url)}&bg=true`);
    if (r?.ok) {
      btn.textContent = r.status === 'downloading' ? '\u2713 Downloading...' : '\u2713 Added';
      btn.style.color = 'var(--green)';
      toast(r.status === 'downloading' ? `Downloading to ${pretty(playlistId)}...` : `Added to ${pretty(playlistId)}`);
      setTimeout(() => { btn.textContent = origText; btn.style.color = ''; btn.disabled = false; }, 5000);
    } else {
      btn.textContent = origText;
      btn.disabled = false;
      toast(r?.error || 'Failed to add song', 'error');
    }
  } catch {
    btn.textContent = origText;
    btn.disabled = false;
    toast('Network error - please try again', 'error');
  }
}

let discoverSearchSeq = 0;

function onDiscoverSearch(q) {
  clearTimeout(discoverSearchTimer);
  const el = $('discoverSearchResults');
  if (!el) return;
  if (!q || q.trim().length < 2) { el.style.display = 'none'; return; }
  const seq = ++discoverSearchSeq;
  discoverSearchTimer = setTimeout(async () => {
    if (!$('discoverSearchResults')) return;
    el.style.display = '';
    el.innerHTML = '<div class="empty"><span class="spinner"></span> Searching...</div>';
    const d = await api(`/discover/search?q=${encodeURIComponent(q.trim())}&max_results=10`);
    if (seq !== discoverSearchSeq) return;
    const el2 = $('discoverSearchResults');
    if (!el2) return;
    if (!d?.songs?.length) {
      el2.innerHTML = `<div class="empty">No results for "${q}"</div>`;
      return;
    }
    el2.innerHTML = `<div class="discover-cat">
      <div class="discover-cat-header">
        <div class="discover-cat-name">Search: "${q}" (${d.songs.length} results)</div>
      </div>
      <div class="discover-songs">${renderDiscoverSongs(d.songs)}</div>
    </div>`;
  }, 400);
}

async function scanTrending() {
  toast('Scanning for trending songs... This may take a minute.');
  const el = $('discoverContent');
  el.innerHTML = '<div class="empty"><span class="spinner"></span> Scanning YouTube for trending songs...</div>';
  const d = await api('/discover/trending');
  if (d) { discoverData = d; renderDiscover(); }
  else { el.innerHTML = '<div class="empty">Scan failed. Try again later.</div>'; }
}

/* ─── SETTINGS DRAWER ─── */
let settingsOpen = false;
let currentSpeed = 1.0;
let currentEq = 'flat';

function toggleSettings() {
  settingsOpen = !settingsOpen;
  $('settingsDrawer').classList.toggle('open', settingsOpen);
}

async function setSpeed(speed) {
  const r = await apiPost('/playback-speed', { speed });
  if (r?.ok) {
    currentSpeed = speed;
    document.querySelectorAll('.speed-btn').forEach(b => {
      b.classList.toggle('active', parseFloat(b.textContent) === speed);
    });
    toast(`Speed: ${speed}x`);
  }
}

async function setEq(preset) {
  const r = await apiPost('/equalizer', { preset });
  if (r?.ok) {
    currentEq = preset;
    document.querySelectorAll('.eq-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.eq === preset);
    });
    toast(`EQ: ${pretty(preset)}`);
  }
}

async function onCrossfadeChange(val) {
  val = parseInt(val);
  $('crossfadeVal').textContent = val === 0 ? 'Off' : val + 's';
  await apiPost('/crossfade', { seconds: val });
}

/* ─── KEYBOARD SHORTCUTS OVERLAY ─── */
let kbdOpen = false;

function toggleKbdOverlay() {
  kbdOpen = !kbdOpen;
  const overlay = $('kbdOverlay');
  overlay.classList.toggle('open', kbdOpen);
  if (kbdOpen && !overlay.dataset.loaded) {
    loadKbdShortcuts();
    overlay.dataset.loaded = 'true';
  }
}

async function loadKbdShortcuts() {
  const shortcuts = await api('/keyboard-shortcuts');
  const grid = $('kbdGrid');
  if (!shortcuts?.length) return;
  grid.innerHTML = shortcuts.map(s =>
    `<div class="kbd-row">
      <span class="kbd-action">${s.action}</span>
      <span class="kbd-key">${s.key.split(' / ').map(k => `<kbd>${k.trim()}</kbd>`).join('')}</span>
    </div>`
  ).join('');
}

/* ─── TOAST ─── */
function toast(msg, type = '') {
  const box = $('toasts');
  const t = document.createElement('div');
  t.className = 'toast' + (type ? ' ' + type : '');
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 4000);
  const sr = $('srLive');
  if (sr) sr.textContent = msg;
}

/* ─── KEYBOARD ─── */
document.addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
  if (kbdOpen && e.key === 'Escape') { toggleKbdOverlay(); return; }
  if (settingsOpen && e.key === 'Escape') { toggleSettings(); return; }
  if (npPanelOpen && e.key === 'Escape') { toggleNowPlayingPanel(); return; }
  if ($('plDetailModal').classList.contains('open') && e.key === 'Escape') { closePlDetail(); return; }
  switch (e.key) {
    case ' ': case 'k': e.preventDefault(); togglePlayPause(); break;
    case 'ArrowRight': if (e.shiftKey) skipTrack(); break;
    case 'ArrowLeft': if (e.shiftKey) previousTrack(); break;
    case 'ArrowUp': e.preventDefault(); onVolumeChange(Math.min(100, vol + 5)); break;
    case 'ArrowDown': e.preventDefault(); onVolumeChange(Math.max(0, vol - 5)); break;
    case 'm': toggleMute(); break;
    case 'l': likeCurrentTrack(); break;
    case 's': toggleShuffle(); break;
    case 'r': toggleRepeat(); break;
    case 'n': toggleNowPlayingPanel(); break;
    case 'p': toggleSettings(); break;
    case '?': e.preventDefault(); toggleKbdOverlay(); break;
    case '/': e.preventDefault(); searchInput?.focus(); break;
  }
});

/* ─── INIT ─── */
buildQuickActions();
refresh();
connectWS();
loadRecentlyPlayed();
setInterval(refresh, 15000);
