/* AG Scorer Web — lightweight responsive frontend for the FastAPI scoring API. */
const API = '';
const state = {
  token: sessionStorage.getItem('ag_scorer_token') || '',
  user: null,
  page: 'overview',
  teams: [], matches: [], tournaments: [], commonPlayers: [],
  activeMatch: null, activeMatchId: null, socket: null,
  pageBusy: false,
};

const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials = value => String(value || 'AG').split(/\s+/).slice(0,2).map(x=>x[0] || '').join('').toUpperCase();
const number = value => Number(value || 0).toLocaleString('en-IN');
const titleCase = value => String(value || '').replaceAll('_',' ').replace(/\b\w/g, c=>c.toUpperCase());
const statusLabel = status => status === 'live' ? 'Live' : status === 'completed' ? 'Completed' : status === 'innings_break' ? 'Innings break' : titleCase(status);
const teamById = id => state.teams.find(t => Number(t.id) === Number(id));
const scoreText = score => score ? `${score.runs}/${score.wickets} <small>(${score.overs})</small>` : '—';

async function api(path, options={}) {
  const headers = {'Content-Type':'application/json', ...(options.headers || {})};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try { response = await fetch(`${API}${path}`, {...options, headers}); }
  catch (_) { throw new Error('Could not reach AG Scorer. Check that the backend server is running.'); }
  let data = null;
  const raw = await response.text();
  if (raw) { try { data = JSON.parse(raw); } catch { data = {detail:raw}; } }
  if (!response.ok) {
    if (response.status === 401 && state.token) logout(false);
    throw new Error(data?.detail || `Request failed (${response.status})`);
  }
  return data;
}

function toast(message, type='success') {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = `toast ${type === 'error' ? 'error' : ''}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(()=>el.remove(), 3400);
}
function setBusy(button, busy, label='Saving…') {
  if (!button) return;
  if (busy) { button.dataset.original = button.innerHTML; button.disabled = true; button.textContent = label; }
  else { button.disabled = false; if (button.dataset.original) button.innerHTML = button.dataset.original; }
}
function showModal(title, body, eyebrow='AG SCORER') {
  $('#modal-title').textContent = title;
  $('#modal-eyebrow').textContent = eyebrow;
  $('#modal-body').innerHTML = body;
  $('#modal-root').classList.remove('hidden');
  $('#modal-root').setAttribute('aria-hidden','false');
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  $('#modal-root').classList.add('hidden');
  $('#modal-root').setAttribute('aria-hidden','true');
  $('#modal-body').innerHTML = '';
  document.body.style.overflow = '';
}
function pageHeading(kicker, title, subtitle, actions='') {
  return `<div class="page-heading"><div><div class="eyebrow green">${esc(kicker)}</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="page-actions">${actions}</div></div>`;
}
function emptyState(symbol, title, detail, action='') {
  return `<div class="empty-state"><div class="empty-symbol">${symbol}</div><strong>${esc(title)}</strong><p>${esc(detail)}</p>${action}</div>`;
}
function matchCard(match) {
  const first = match.first_innings, second = match.second_innings;
  const scoreForTeam = teamId => {
    if (Number(match.innings) === 1) return Number(match.batting_team.id) === Number(teamId) ? match.score : null;
    if (Number(match.batting_team.id) === Number(teamId)) return match.score;
    if (Number(match.bowling_team.id) === Number(teamId)) return first;
    return null;
  };
  const showA = scoreForTeam(match.team_a.id), showB = scoreForTeam(match.team_b.id);
  const aScore = showA ? `${showA.runs}/${showA.wickets}` : 'Yet to bat';
  const bScore = showB ? `${showB.runs}/${showB.wickets}` : 'Yet to bat';
  return `<article class="match-card" data-action="open-match" data-id="${match.id}">
    <div class="match-card-top"><div class="match-competition">${esc(match.venue || match.format || 'Cricket match')}</div><span class="status-pill ${esc(match.status)}">${esc(statusLabel(match.status))}</span></div>
    <div class="match-sides"><div class="team-score"><strong>${esc(match.team_a.short_name || match.team_a.name)}</strong><span>${esc(aScore)}</span></div><div class="vs-mark">VS</div><div class="team-score right"><strong>${esc(match.team_b.short_name || match.team_b.name)}</strong><span>${esc(bScore)}</span></div></div>
    <div class="match-card-bottom"><span>${esc(match.title)}</span><strong>${match.status === 'live' ? 'OPEN SCORER ↗' : match.status === 'completed' ? 'VIEW SCORECARD ↗' : 'CONTINUE ↗'}</strong></div>
  </article>`;
}

async function loadCollections() {
  const [teams, matches, tournaments, commonPlayers] = await Promise.all([
    api('/teams'), api('/matches'), api('/tournaments'), api('/players/common')
  ]);
  state.teams = teams; state.matches = matches; state.tournaments = tournaments; state.commonPlayers = commonPlayers;
  $('#shared-nav-count').textContent = commonPlayers.length;
}
async function startApp() {
  try {
    state.user = await api('/auth/me');
    $('#auth-screen').classList.add('hidden');
    $('#app-shell').classList.remove('hidden');
    $('#user-name').textContent = state.user.name;
    $('#user-email').textContent = state.user.email;
    $('#user-avatar').textContent = initials(state.user.name);
    await loadCollections();
    await navigate(state.page || 'overview');
  } catch (error) {
    if (state.token) toast(error.message, 'error');
    $('#auth-screen').classList.remove('hidden');
    $('#app-shell').classList.add('hidden');
  }
}
function logout(showMessage=true) {
  if (state.socket) { state.socket.close(); state.socket = null; }
  state.token = ''; state.user = null; state.activeMatch = null;
  sessionStorage.removeItem('ag_scorer_token');
  $('#app-shell').classList.add('hidden');
  $('#auth-screen').classList.remove('hidden');
  if (showMessage) toast('You have signed out.');
}

// Authentication
let registerMode = false;
function setAuthMode(register) {
  registerMode = register;
  $('#auth-name-wrap').classList.toggle('hidden', !register);
  $('#auth-title').textContent = register ? 'Create your account' : 'Sign in to your account';
  $('#auth-subtitle').textContent = register ? 'Set up your own scoring workspace.' : 'Pick up where your cricket left off.';
  $('#auth-submit').innerHTML = register ? 'Create account <span>↗</span>' : 'Sign in <span>↗</span>';
  $('#auth-switch-copy').textContent = register ? 'Already have an account?' : 'New to AG Scorer?';
  $('#auth-switch').textContent = register ? 'Sign in' : 'Create account';
  $('#auth-password').autocomplete = register ? 'new-password' : 'current-password';
  $('#auth-error').classList.add('hidden');
}
$('#auth-switch').addEventListener('click',()=>setAuthMode(!registerMode));
$('#auth-form').addEventListener('submit', async event=>{
  event.preventDefault(); const button=$('#auth-submit'); setBusy(button,true,'Please wait…'); $('#auth-error').classList.add('hidden');
  try {
    const payload = registerMode
      ? await api('/auth/register',{method:'POST',body:JSON.stringify({name:$('#auth-name').value.trim(),email:$('#auth-email').value.trim(),password:$('#auth-password').value})})
      : await api('/auth/login',{method:'POST',body:JSON.stringify({email:$('#auth-email').value.trim(),password:$('#auth-password').value})});
    state.token=payload.access_token; sessionStorage.setItem('ag_scorer_token',state.token); state.page='overview';
    await startApp();
  } catch(error) { $('#auth-error').textContent=error.message; $('#auth-error').classList.remove('hidden'); }
  finally { setBusy(button,false); }
});

// Navigation and shell
async function navigate(page) {
  state.page = page;
  $$('.nav-item').forEach(item=>item.classList.toggle('active',item.dataset.page===page));
  $('#page-crumb').textContent = ({overview:'Overview',matches:'Matches',teams:'Teams',players:'Players',mvp:'MVP rankings',tournaments:'Tournaments',scorer:'Live scorer',profile:'Profile'})[page] || 'Overview';
  if (page !== 'scorer' && state.socket) { state.socket.close(); state.socket=null; }
  try {
    if (page==='overview') await renderOverview();
    else if (page==='matches') await renderMatches();
    else if (page==='teams') await renderTeams();
    else if (page==='players') await renderPlayers();
    else if (page==='mvp') await renderMvpRankings();
    else if (page==='tournaments') await renderTournaments();
    else if (page==='scorer') await renderScorer();
    else if (page==='profile') renderProfile();
  } catch(error) {
    $('#page-content').innerHTML = pageHeading('WORKSPACE','Something went wrong','The page could not be loaded.') + `<div class="panel">${emptyState('!','Could not load this view',error.message,'<button class="btn btn-outline" data-action="retry-page">Try again</button>')}</div>`;
  }
}
$('#main-nav').addEventListener('click',event=>{const item=event.target.closest('[data-page]');if(item)navigate(item.dataset.page);});
$('#profile-button').addEventListener('click',()=>navigate('profile'));
$('#global-create-match').addEventListener('click',()=>showCreateMatch());
$('.mobile-profile').addEventListener('click',()=>navigate('profile'));
$('#modal-root').addEventListener('click',event=>{if(event.target.matches('[data-close-modal]'))closeModal();});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeModal();});

async function renderOverview() {
  if (!state.teams.length && !state.matches.length) await loadCollections();
  const live=state.matches.filter(m=>m.status==='live');
  const completed=state.matches.filter(m=>m.status==='completed');
  const recent=state.matches.slice(0,4);
  $('#page-content').innerHTML = `${pageHeading('YOUR CRICKET WORKSPACE','The game, in your hands.','A clean view of your matches, teams and player records.',`<button class="btn btn-primary" data-action="create-match">＋ Create match</button>`)}
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-top">Total matches <span class="metric-symbol">◉</span></div><div class="metric-value">${state.matches.length}</div><div class="metric-foot">All matches in your workspace</div></div>
      <div class="metric-card"><div class="metric-top">Live right now <span class="metric-symbol">●</span></div><div class="metric-value">${live.length}</div><div class="metric-foot">Matches currently being scored</div></div>
      <div class="metric-card"><div class="metric-top">Teams managed <span class="metric-symbol">♧</span></div><div class="metric-value">${state.teams.length}</div><div class="metric-foot">Your team squads and rosters</div></div>
      <div class="metric-card"><div class="metric-top">Shared players <span class="metric-symbol">◎</span></div><div class="metric-value">${state.commonPlayers.length}</div><div class="metric-foot">Available to play for either team</div></div>
    </div>
    <div class="content-grid"><section class="panel"><div class="panel-header"><div><h3>Recent matches</h3><p>Your latest scorecards and live action</p></div><button class="text-action" data-page="matches">VIEW ALL ↗</button></div>
      ${recent.length?`<div class="match-list">${recent.map(matchCard).join('')}</div>`:emptyState('◉','No matches yet','Create your first match and start recording every delivery.','<button class="btn btn-primary" data-action="create-match">Create a match</button>')}
    </section><aside class="panel"><div class="panel-header"><div><h3>Quick actions</h3><p>Keep your cricket moving</p></div></div><div class="quick-actions">
      <button class="quick-action" data-action="create-match"><span class="quick-icon">＋</span><b>New match</b><small>Set up a fixture</small></button>
      <button class="quick-action" data-action="create-team"><span class="quick-icon">♧</span><b>Create team</b><small>Build a squad</small></button>
      <button class="quick-action" data-action="create-player"><span class="quick-icon">◎</span><b>Add player</b><small>Grow a roster</small></button>
      <button class="quick-action" data-action="create-common"><span class="quick-icon">⇄</span><b>Shared player</b><small>Available to both sides</small></button>
    </div><div class="panel-header" style="margin:22px 0 10px"><div><h3>Your workspace</h3><p>Quick account overview</p></div></div><div class="innings-score-list"><div class="innings-score-row"><span>Completed matches</span><strong>${completed.length}</strong></div><div class="innings-score-row"><span>Tournaments</span><strong>${state.tournaments.length}</strong></div><div class="innings-score-row"><span>Shared player profiles</span><strong>${state.commonPlayers.length}</strong></div></div></aside></div>`;
}
async function renderMatches() {
  await loadCollections();
  $('#page-content').innerHTML=`${pageHeading('MATCH CENTRE','Matches','Every fixture, live innings and final result.',`<button class="btn btn-primary" data-action="create-match">＋ New match</button>`)}
  <div class="metric-grid"><div class="metric-card"><div class="metric-top">All matches <span class="metric-symbol">◉</span></div><div class="metric-value">${state.matches.length}</div></div><div class="metric-card"><div class="metric-top">Live <span class="metric-symbol">●</span></div><div class="metric-value">${state.matches.filter(m=>m.status==='live').length}</div></div><div class="metric-card"><div class="metric-top">Innings break <span class="metric-symbol">Ⅱ</span></div><div class="metric-value">${state.matches.filter(m=>m.status==='innings_break').length}</div></div><div class="metric-card"><div class="metric-top">Completed <span class="metric-symbol">✓</span></div><div class="metric-value">${state.matches.filter(m=>m.status==='completed').length}</div></div></div>
  ${state.matches.length?`<div class="match-list">${state.matches.map(matchCard).join('')}</div>`:`<div class="panel">${emptyState('◉','No matches added','Create a match to start scoring with AG Scorer.','<button class="btn btn-primary" data-action="create-match">Create a match</button>')}</div>`}`;
}
async function renderTeams() {
  await loadCollections();
  const playersByTeam = await Promise.all(state.teams.map(async team=>({team,players:await api(`/teams/${team.id}/players`)})));
  $('#page-content').innerHTML=`${pageHeading('SQUAD MANAGEMENT','Your teams','Manage team details, player rosters and shared squad members.',`<button class="btn btn-outline" data-action="create-player">＋ Add player</button><button class="btn btn-primary" data-action="create-team">＋ New team</button>`)}
  ${playersByTeam.length?`<div class="team-grid">${playersByTeam.map(({team,players})=>`<article class="team-card"><div class="team-card-head"><div class="team-monogram">${esc(team.short_name)}</div><div><h3>${esc(team.name)}</h3><p>${esc(team.short_name)} · ${players.length} players available</p></div></div><div class="roster-list">${players.slice(0,5).map(p=>`<div class="roster-row" data-action="player-stats" data-id="${p.id}" style="cursor:pointer"><span class="player-cell"><span class="player-avatar">${esc(initials(p.name))}</span>${esc(p.name)}</span>${p.is_common?'<span class="badge common">SHARED</span>':`<span class="muted">#${p.jersey_number||'—'}</span>`}</div>`).join('')}${players.length>5?`<div class="hint">+ ${players.length-5} more players</div>`:''}${players.length===0?'<div class="hint">No players added yet.</div>':''}</div><div class="team-card-foot"><span>${players.filter(p=>p.is_common).length} shared · ${players.filter(p=>!p.is_common).length} team players</span><button class="text-action" data-action="add-player-to-team" data-id="${team.id}">ADD PLAYER ＋</button></div></article>`).join('')}</div>`:`<div class="panel">${emptyState('♧','Build your first team','Create a team and add players to start setting up matches.','<button class="btn btn-primary" data-action="create-team">Create team</button>')}</div>`}`;
}
async function renderPlayers() {
  await loadCollections();
  const html = state.commonPlayers.length?`<div class="player-grid">${state.commonPlayers.map(p=>`<article class="shared-player-card"><span class="player-avatar">${esc(initials(p.name))}</span><div class="player-details"><strong>${esc(p.name)}</strong><small>${esc(p.role)} · Home roster: ${esc(p.home_team)}</small></div><span class="badge common">SHARED</span><button class="icon-button" data-action="player-stats" data-id="${p.id}" title="View stats">↗</button></article>`).join('')}</div>`:emptyState('⇄','No shared players yet','Create a shared player once and select that same profile in either team’s lineup.','<button class="btn btn-primary" data-action="create-common">Add shared player</button>');
  $('#page-content').innerHTML=`${pageHeading('PLAYER DIRECTORY','Players & shared roster','A shared player has one profile and one statistics record, but is selectable for either of your teams.',`<button class="btn btn-outline" data-action="create-player">＋ Team player</button><button class="btn btn-primary" data-action="create-common">＋ Shared player</button>`)}
  <div class="shared-callout"><span class="shared-symbol">⇄</span><div><strong>One player. Either team.</strong><p>Shared players are visible in every team’s lineup selector. Their batting and bowling statistics stay on the same player profile rather than being split into duplicate records.</p></div></div>
  <div class="panel"><div class="panel-header"><div><h3>Shared players</h3><p>${state.commonPlayers.length} player profiles available across your teams</p></div><span class="badge common">CROSS-TEAM ROSTER</span></div>${html}</div>`;
}
async function renderMvpRankings() {
  const data = await api('/mvp-rankings');
  const rows = data.rankings || [];
  const leader = rows[0];
  $('#page-content').innerHTML = `${pageHeading('PLAYER PERFORMANCE','MVP rankings','Leaderboard based on recorded batting and bowling performances.')}
    ${leader ? `<div class="metric-grid"><div class="metric-card"><div class="metric-top">Current leader <span class="metric-symbol">♛</span></div><div class="metric-value" style="font-size:20px">${esc(leader.name)}</div><div class="metric-foot">${leader.points} MVP points</div></div><div class="metric-card"><div class="metric-top">Matches represented</div><div class="metric-value">${leader.matches}</div><div class="metric-foot">For the current leader</div></div><div class="metric-card"><div class="metric-top">Runs scored</div><div class="metric-value">${leader.runs}</div><div class="metric-foot">For the current leader</div></div><div class="metric-card"><div class="metric-top">Wickets taken</div><div class="metric-value">${leader.wickets}</div><div class="metric-foot">For the current leader</div></div></div>` : ''}
    <section class="panel"><div class="panel-header"><div><h3>All-player leaderboard</h3><p>${rows.length} players ranked from your saved match deliveries</p></div><span class="badge">MVP</span></div>
      ${rows.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Rank</th><th>Player</th><th>Matches</th><th>Runs</th><th>4s</th><th>6s</th><th>Wickets</th><th>MVP pts</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${r.rank}</strong></td><td><strong>${esc(r.name)}</strong>${r.is_common?` <span class="badge common">Shared</span>`:''}</td><td>${r.matches}</td><td>${r.runs}</td><td>${r.fours}</td><td>${r.sixes}</td><td>${r.wickets}</td><td><strong>${r.points}</strong></td></tr>`).join('')}</tbody></table></div>` : emptyState('♛','No MVP rankings yet','Rankings will appear after runs or wickets are recorded in your matches.')}
      <p class="hint" style="margin-top:14px">Points: ${esc(data.points_formula)}. Fielding points are not included because catches and run-outs are not recorded separately.</p>
    </section>`;
}

async function renderTournaments() {
  await loadCollections();
  const standings = await Promise.all(state.tournaments.map(async t=>({t,rows:await api(`/tournaments/${t.id}/standings`)})));
  $('#page-content').innerHTML=`${pageHeading('COMPETITION HUB','Tournaments','Create competitions and keep a running table of team results.',`<button class="btn btn-primary" data-action="create-tournament">＋ New tournament</button>`)}
    ${standings.length?`<div class="tournament-grid">${standings.map(({t,rows})=>`<article class="tournament-card"><div class="team-card-head"><div class="team-monogram">♜</div><div><h3>${esc(t.name)}</h3><p>${esc(t.format)}${t.venue?' · '+esc(t.venue):''}</p></div></div><div class="team-card-foot"><span>${t.matches_count} matches · ${rows.length} teams</span><span class="badge">${esc(t.format)}</span></div>${rows.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Team</th><th>P</th><th>W</th><th>Pts</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.team)}</strong></td><td>${r.played}</td><td>${r.won}</td><td><strong>${r.points}</strong></td></tr>`).join('')}</tbody></table></div>`:'<div class="hint">Add this tournament while creating a match to populate the standings.</div>'}</article>`).join('')}</div>`:`<div class="panel">${emptyState('♜','No tournaments created','Create a competition, then attach matches to it to build the points table.','<button class="btn btn-primary" data-action="create-tournament">Create tournament</button>')}</div>`}`;
}
function renderProfile() {
  $('#page-content').innerHTML=`${pageHeading('ACCOUNT SETTINGS','Your profile','Account and session details.')}
  <div class="panel profile-panel"><div class="profile-info"><span class="avatar">${esc(initials(state.user?.name))}</span><div><strong>${esc(state.user?.name)}</strong><small>${esc(state.user?.email)}</small></div></div><div class="innings-score-list"><div class="innings-score-row"><span>Teams</span><strong>${state.teams.length}</strong></div><div class="innings-score-row"><span>Matches</span><strong>${state.matches.length}</strong></div><div class="innings-score-row"><span>Shared players</span><strong>${state.commonPlayers.length}</strong></div></div><div style="margin-top:18px"><button class="btn btn-outline" data-action="logout">Sign out of AG Scorer</button></div></div>`;
}

// Team, player and tournament creation
function createTeamModal() {
  showModal('Create a team',`<form id="create-team-form" class="modal-form"><label class="field">Team name<input name="name" placeholder="e.g. Delhi Strikers" minlength="2" required></label><label class="field">Short name / code<input name="short_name" placeholder="e.g. DLS" maxlength="12" minlength="2" required></label><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Create team</button></div></form>`,'TEAM MANAGEMENT');
}
function createPlayerModal(preselectedTeam=null) {
  if (!state.teams.length) { toast('Create a team before adding a team player.','error'); return; }
  showModal('Add a team player',`<form id="create-player-form" class="modal-form"><label class="field">Team<select name="team_id" required>${state.teams.map(t=>`<option value="${t.id}" ${Number(t.id)===Number(preselectedTeam)?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label><label class="field">Player name<input name="name" placeholder="Full player name" minlength="2" required></label><div class="form-row"><label class="field">Role<select name="role"><option>Batter</option><option>Bowler</option><option>All-rounder</option><option>Wicketkeeper</option></select></label><label class="field">Jersey number<input name="jersey_number" type="number" min="0" max="999" value="0"></label></div><p class="hint">This player will be part of the selected team only. Use “Shared player” when the same profile should be selectable for either team.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Add player</button></div></form>`,'SQUAD MANAGEMENT');
}
function createCommonPlayerModal() {
  if (!state.teams.length) { toast('Create at least one team before adding a shared player.','error'); return; }
  showModal('Add a shared player',`<form id="create-common-form" class="modal-form"><div class="shared-callout" style="margin:0"><span class="shared-symbol">⇄</span><div><strong>One player profile for both teams</strong><p>The selected home team stores the player record. The player will also appear in every other team’s lineup selector.</p></div></div><label class="field">Home roster<select name="home_team_id" required>${state.teams.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></label><label class="field">Player name<input name="name" placeholder="Full player name" minlength="2" required></label><div class="form-row"><label class="field">Role<select name="role"><option>All-rounder</option><option>Batter</option><option>Bowler</option><option>Wicketkeeper</option></select></label><label class="field">Jersey number<input name="jersey_number" type="number" min="0" max="999" value="0"></label></div><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Create shared player</button></div></form>`,'SHARED ROSTER');
}
function createTournamentModal() {
  showModal('Create a tournament',`<form id="create-tournament-form" class="modal-form"><label class="field">Tournament name<input name="name" placeholder="e.g. AG Premier League" minlength="2" required></label><div class="form-row"><label class="field">Format<select name="format"><option>League</option><option>Knockout</option><option>Group + Knockout</option><option>Friendly Series</option></select></label><label class="field">Venue<input name="venue" placeholder="Venue / city"></label></div><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Create tournament</button></div></form>`,'COMPETITION HUB');
}

async function showCreateMatch() {
  if (state.teams.length<2) { toast('Create at least two teams before setting up a match.','error'); return; }
  showModal('Set up a match',`<form id="create-match-form" class="modal-form">
    <label class="field">Match title<input name="title" placeholder="Team A vs Team B" required></label>
    <div class="form-row"><label class="field">Team A<select id="match-team-a" name="team_a_id">${state.teams.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></label><label class="field">Team B<select id="match-team-b" name="team_b_id">${state.teams.map((t,i)=>`<option value="${t.id}" ${i===1?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label></div>
    <div class="form-row"><label class="field">Format<select name="match_format"><option>T20</option><option>T10</option><option>ODI</option><option>Test</option><option>Custom</option></select></label><label class="field">Overs<input name="total_overs" type="number" min="1" max="90" value="20" required></label></div>
    <label class="field">Venue<input name="venue" placeholder="Ground / location"></label>
    <div class="form-row"><label class="field">Toss winner<select name="toss_winner_id" id="match-toss-winner"></select></label><label class="field">Toss decision<select name="toss_decision" id="match-toss-decision"><option value="bat">Bat first</option><option value="bowl">Bowl first</option></select></label></div>
    <div class="mode-choice">
      <label class="mode-choice-head"><input id="match-single-batter" type="checkbox" name="single_batter_mode"><span><strong>Single-batter mode</strong><small>Use one batter only — no non-striker and no strike rotation.</small></span></label>
    </div>
    <div class="eyebrow green">OPENING LINE-UP</div><div id="match-lineup-fields" class="form-row"><div class="hint">Loading team players…</div></div>
    <label class="field">Tournament (optional)<select name="tournament_id"><option value="">No tournament</option>${state.tournaments.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></label>
    <p class="hint">A shared player keeps one profile and can be selected in either team’s player list, including both sides of this fixture. Career stats stay combined.</p>
    <div class="form-error hidden" id="match-form-error"></div><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Create match</button></div>
  </form>`,'MATCH SETUP');
  const teamA=$('#match-team-a'), teamB=$('#match-team-b'), winner=$('#match-toss-winner'), decision=$('#match-toss-decision'), solo=$('#match-single-batter');
  function fillWinner() {
    const a=teamById(teamA.value), b=teamById(teamB.value);
    winner.innerHTML=`<option value="${a.id}">${esc(a.name)}</option><option value="${b.id}">${esc(b.name)}</option>`;
  }
  async function fillLineup() {
    const aId=Number(teamA.value), bId=Number(teamB.value);
    if(aId===bId){$('#match-lineup-fields').innerHTML='<div class="form-error">Select two different teams.</div>';return;}
    const [aPlayers,bPlayers]=await Promise.all([api(`/teams/${aId}/players`),api(`/teams/${bId}/players`)]);
    const tossId=Number(winner.value || aId), batFirst=decision.value==='bat'?tossId:(tossId===aId?bId:aId), bowlFirst=batFirst===aId?bId:aId;
    const battingPlayers=batFirst===aId?aPlayers:bPlayers, bowlingPlayers=bowlFirst===aId?aPlayers:bPlayers;
    const pOptions=players=>players.map(p=>`<option value="${p.id}">${esc(p.name)}${p.is_common?' · SHARED':''}</option>`).join('');
    const submit=$('#create-match-form button[type=submit]');
    const minBatters=solo.checked?1:2;
    if(battingPlayers.length<minBatters || bowlingPlayers.length<1) {
      $('#match-lineup-fields').innerHTML=`<div class="scorer-notice" style="grid-column:1/-1">Add at least ${minBatters} batting player${minBatters===1?'':'s'} and one bowling player to the selected teams. Shared players are included in both rosters.</div>`;
      submit.disabled=true;
    } else {
      $('#match-lineup-fields').innerHTML=`<label class="field">${solo.checked?'Solo batter':'Striker'}<select name="striker_id">${pOptions(battingPlayers)}</select></label>${solo.checked?'':`<label class="field">Non-striker<select name="non_striker_id">${pOptions(battingPlayers)}</select></label>`}<label class="field" style="grid-column:1/-1">Opening bowler<select name="bowler_id">${pOptions(bowlingPlayers)}</select></label>`;
      submit.disabled=false;
    }
    const title=$('#create-match-form [name=title]'); if(!title.value) title.value=`${teamById(aId).name} vs ${teamById(bId).name}`;
  }
  teamA.addEventListener('change',()=>{fillWinner();fillLineup();});
  teamB.addEventListener('change',()=>{fillWinner();fillLineup();});
  winner.addEventListener('change',fillLineup); decision.addEventListener('change',fillLineup); solo.addEventListener('change',fillLineup);
  fillWinner(); await fillLineup();
}

// Match scorer
async function openMatch(id) {
  if(state.socket){state.socket.close();state.socket=null;}
  state.activeMatchId=Number(id); state.activeMatch=await api(`/matches/${id}`);
  state.page='scorer'; await navigate('scorer'); connectMatchSocket(id);
}
function connectMatchSocket(id) {
  if(state.socket)state.socket.close();
  if(!state.token)return;
  const scheme=location.protocol==='https:'?'wss':'ws';
  try {
    state.socket=new WebSocket(`${scheme}://${location.host}/ws/matches/${id}?token=${encodeURIComponent(state.token)}`);
    state.socket.onmessage=event=>{try{const msg=JSON.parse(event.data);if(msg.match){state.activeMatch=msg.match;renderScorer();}}catch(_){}};
    state.socket.onclose=()=>{state.socket=null;};
  }catch(_){state.socket=null;}
}
async function refreshActiveMatch() {
  state.activeMatch=await api(`/matches/${state.activeMatchId}`);
  renderScorer();
}
function scorecardTable(score, kind) {
  const batting=kind==='batting'; const rows=batting?(score?.batting||[]):(score?.bowling||[]);
  if(!batting) return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Bowler</th><th>O</th><th>R</th><th>W</th><th>ECO</th></tr></thead><tbody>${rows.length?rows.map(r=>`<tr><td><strong>${esc(r.name)}</strong></td><td>${esc(r.overs)}</td><td>${r.runs}</td><td>${r.wickets}</td><td>${r.economy}</td></tr>`).join(''):'<tr><td colspan="5" class="muted">No bowling figures yet.</td></tr>'}</tbody></table></div>`;
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Batter</th><th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th></tr></thead><tbody>${rows.length?rows.map(r=>`<tr><td><strong>${esc(r.name)}</strong> ${r.dismissal!=='not out'?`<small class="muted">${esc(titleCase(r.dismissal))}</small>`:'<small class="muted">not out</small>'}</td><td>${r.runs}</td><td>${r.balls}</td><td>${r.fours}</td><td>${r.sixes}</td><td>${r.strike_rate}</td></tr>`).join(''):'<tr><td colspan="6" class="muted">No batting figures yet.</td></tr>'}</tbody></table></div>`;
}
async function renderScorer() {
  if(!state.activeMatch && state.activeMatchId) state.activeMatch=await api(`/matches/${state.activeMatchId}`);
  const m=state.activeMatch;
  if(!m){$('#page-content').innerHTML=emptyState('◉','No match selected','Choose a match from the match centre.');return;}
  const score=m.score, first=m.first_innings, second=m.second_innings;
  const scoringLocked = m.status!=='live' || !m.bowler || !m.striker || (!m.single_batter_mode && !m.non_striker);
  const lockAttr = scoringLocked ? 'disabled' : '';
  const runButtons=[0,1,2,3,4,5,6].map(run=>`<button class="run-button ${run===4||run===6?'accent':''}" ${lockAttr} data-action="score-run" data-runs="${run}">${run}</button>`).join('');
  const lastOver=(m.last_over||[]).map(ball=>`<span class="ball-chip ${ball==='W'?'wicket':ball==='4'||ball==='6'?'boundary':''}">${esc(ball)}</span>`).join('') || '<span class="hint">Balls will appear here.</span>';
  const actions = m.status==='live' ? `<button class="btn btn-outline" data-action="undo-ball">↶ Undo last ball</button>${m.single_batter_mode?'':`<button class="btn btn-quiet" data-action="swap-batters">⇄ Swap batters</button>`}` : m.status==='innings_break' ? `<button class="btn btn-primary" data-action="next-innings">Start second innings ↗</button>` : `<span class="badge neutral">MATCH ${esc(statusLabel(m.status).toUpperCase())}</span>`;
  const target = m.innings===2 ? `<div class="score-stat"><small>TARGET</small><strong>${m.target}</strong></div><div class="score-stat"><small>NEEDED</small><strong>${m.runs_required}</strong></div>` : '';
  $('#page-content').innerHTML=`${pageHeading('LIVE MATCH CENTRE',m.title,`${m.venue||'Venue not set'} · ${m.format} · ${m.total_overs} overs`,actions)}
    <div class="scorer-shell"><div><section class="score-hero"><div class="score-hero-top"><div class="eyebrow">INNINGS ${m.innings} · ${esc(m.batting_team.name)} BATTING</div><span class="status-pill ${esc(m.status)}">${esc(statusLabel(m.status))}</span></div><div class="score-hero-main"><div class="big-score">${score.runs}<small>/${score.wickets}</small></div><div class="score-overs">${esc(score.overs)} overs</div></div><div class="score-context">${m.innings===2?`Chasing ${m.target} · ${m.runs_required} runs required`:`${esc(m.batting_team.short_name)} vs ${esc(m.bowling_team.short_name)}`}</div><div class="score-hero-bottom"><div class="score-stat"><small>RUN RATE</small><strong>${score.legal_balls?((score.runs*6)/score.legal_balls).toFixed(2):'0.00'}</strong></div><div class="score-stat"><small>EXTRAS</small><strong>${score.extras}</strong></div><div class="score-stat"><small>OVERS LEFT</small><strong>${Math.max(0,m.total_overs*6-score.legal_balls)/6|0}.${Math.max(0,m.total_overs*6-score.legal_balls)%6}</strong></div>${target}</div></section>
      <section class="panel scoring-panel"><div class="panel-header"><div><h3>Ball-by-ball scoring</h3><p>Tap the outcome of the delivery</p></div><span class="badge ${m.status==='live'?'':'neutral'}">${m.status==='live'?'SCORING OPEN':'SCORING LOCKED'}</span></div>
        ${m.status==='live'?`${!m.bowler?`<div class="scorer-notice" style="margin-bottom:12px">Over complete. Select the next bowler on the right to continue scoring.</div>`:''}<div class="run-grid">${runButtons}<button class="run-button danger subtle" ${lockAttr} data-action="wicket">WICKET</button><button class="run-button subtle" ${lockAttr} data-action="extra" data-extra="wide">WIDE</button><button class="run-button subtle" ${lockAttr} data-action="extra" data-extra="no_ball">NO BALL</button><button class="run-button subtle" ${lockAttr} data-action="extra" data-extra="bye">BYE</button><button class="run-button subtle" ${lockAttr} data-action="extra" data-extra="leg_bye">LEG BYE</button><button class="run-button subtle" ${lockAttr} data-action="extra" data-extra="penalty">PENALTY</button></div>`:`<div class="scorer-notice">This match is ${esc(statusLabel(m.status).toLowerCase())}. Scoring is locked. You can still review the scorecard.</div>`}
      </section>
      <section class="panel" style="margin-top:15px"><div class="panel-header"><div><h3>Current over</h3><p>Delivery sequence</p></div><span class="hint">${score.overs} overs</span></div><div class="last-over">${lastOver}</div></section>
      <section class="panel" style="margin-top:15px"><div class="panel-header"><div><h3>Batting scorecard</h3><p>${esc(m.batting_team.name)}</p></div></div>${scorecardTable(score,'batting')}<div class="panel-header" style="margin:18px 0 6px"><div><h3>Bowling figures</h3><p>${esc(m.bowling_team.name)}</p></div></div>${scorecardTable(score,'bowling')}</section>
    </div><aside><section class="panel"><div class="panel-header"><div><h3>At the crease</h3><p>Current player positions</p></div></div><div class="active-players"><div class="active-player"><div><small>${m.single_batter_mode?'Solo batter':'Striker'}</small><strong>${esc(m.striker?.name||'Not selected')}</strong></div><span class="badge">${m.single_batter_mode?'BATTER':'ON STRIKE'}</span></div>${m.single_batter_mode?`<div class="solo-mode-note">SINGLE-BATTER MODE · NO NON-STRIKER</div>`:`<div class="active-player"><div><small>Non-striker</small><strong>${esc(m.non_striker?.name||'Not selected')}</strong></div><span class="badge neutral">NON-STRIKER</span></div>`}<div class="active-player"><div><small>Bowler</small><strong>${esc(m.bowler?.name||'Select next bowler')}</strong></div><span class="badge neutral">BOWLING</span></div></div>
      ${m.status==='live'?`<div style="margin-top:15px"><button class="btn btn-outline" style="width:100%" data-action="change-batters">Change batters</button>${!m.bowler?`<button class="btn btn-primary" style="width:100%;margin-top:8px" data-action="change-bowler">Select next bowler</button>`:''}</div>`:''}
    </section><section class="panel" style="margin-top:15px"><div class="panel-header"><div><h3>Match summary</h3><p>Innings overview</p></div></div><div class="innings-score-list"><div class="innings-score-row"><span>${esc(m.team_a.short_name)}</span><strong>${teamInningsScore(m,m.team_a.id)}</strong></div><div class="innings-score-row"><span>${esc(m.team_b.short_name)}</span><strong>${teamInningsScore(m,m.team_b.id)}</strong></div></div>${m.result_text?`<div class="scorer-notice" style="margin-top:12px">${esc(m.result_text)}</div>`:''}</section>
    <section class="panel" style="margin-top:15px"><div class="panel-header"><div><h3>Match controls</h3><p>Live match administration</p></div></div><div class="quick-actions"><button class="quick-action" data-action="refresh-match"><span class="quick-icon">↻</span><b>Refresh</b><small>Reload score</small></button><button class="quick-action" data-action="scorecard-view"><span class="quick-icon">▤</span><b>Scorecard</b><small>Full innings view</small></button></div></section>
    </aside></div>`;
}
function teamInningsScore(m,teamId) {
  let s=null;
  if(Number(m.innings)===1) {
    if(Number(m.batting_team.id)===Number(teamId)) s=m.score;
  } else {
    if(Number(m.batting_team.id)===Number(teamId)) s=m.score;
    else if(Number(m.bowling_team.id)===Number(teamId)) s=m.first_innings;
  }
  return s?`${s.runs}/${s.wickets} (${s.overs})`:'Yet to bat';
}
async function teamPlayers(teamId) { return await api(`/teams/${teamId}/players`); }
function selectOptions(players, excluded=[]) {return players.filter(p=>!excluded.includes(Number(p.id))).map(p=>`<option value="${p.id}">${esc(p.name)}${p.is_common?' · SHARED':''}</option>`).join('');}
async function scoreBall(data) {
  const m=state.activeMatch; if(!m)return;
  try { state.activeMatch=await api(`/matches/${m.id}/balls`,{method:'POST',body:JSON.stringify(data)}); renderScorer(); }
  catch(error){toast(error.message,'error');}
}
async function chooseWicket() {
  const m=state.activeMatch; const players=await teamPlayers(m.batting_team.id);
  const dismissedIds=m.dismissed_player_ids||[];
  const available=players.filter(p=>!dismissedIds.includes(Number(p.id)) && Number(p.id)!==Number(m.striker?.id) && Number(p.id)!==Number(m.non_striker?.id));
  const dismissedOptions=m.single_batter_mode?`<option value="${m.striker.id}">${esc(m.striker.name)} (Solo batter)</option>`:`<option value="${m.striker.id}">${esc(m.striker.name)} (Striker)</option><option value="${m.non_striker.id}">${esc(m.non_striker.name)} (Non-striker)</option>`;
  showModal('Record a wicket',`<form id="wicket-form" class="modal-form"><div class="form-row"><label class="field">Dismissal type<select name="wicket_type"><option value="bowled">Bowled</option><option value="caught">Caught</option><option value="lbw">LBW</option><option value="run_out">Run out</option><option value="stumped">Stumped</option><option value="hit_wicket">Hit wicket</option><option value="retired_hurt">Retired hurt</option><option value="obstructing_field">Obstructing the field</option><option value="hit_twice">Hit the ball twice</option></select></label><label class="field">Dismissed batter<select name="dismissed_player_id">${dismissedOptions}</select></label></div><label class="field">Incoming batter<select name="new_batter_id"><option value="">Choose batter</option>${selectOptions(available)}</select></label><p class="hint">Choose the incoming batter. In solo mode, the new batter takes the only batting position.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Record wicket</button></div></form>`,'BALL ENTRY');
}
async function extraModal(type) {
  const label=titleCase(type);
  const defaultExtras=type==='penalty'?5:1;
  const defaultRunning=(type==='bye'||type==='leg_bye')?1:0;
  const minExtras=type==='penalty'?0:1;
  showModal(`Record ${label.toLowerCase()}`,`<form id="extra-form" class="modal-form"><input type="hidden" name="extra_type" value="${type}"><div class="form-row"><label class="field">Runs off the bat<input name="runs_bat" type="number" min="0" max="6" value="0"></label><label class="field">Total extras<input name="extra_runs" type="number" min="${minExtras}" max="10" value="${defaultExtras}" required></label></div><label class="field">Completed running runs<input name="running_runs" type="number" min="0" max="6" value="${defaultRunning}"></label><p class="hint">Total extras are added to the team score. Completed running runs are used only for strike rotation. For wides/no-balls, include the penalty in total extras and enter completed runs separately. Wides and no-balls are not legal balls.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Save delivery</button></div></form>`,'BALL ENTRY');
}
async function chooseBowler() {
  const m=state.activeMatch; const players=await teamPlayers(m.bowling_team.id);
  showModal('Select next bowler',`<form id="bowler-form" class="modal-form"><label class="field">Bowler<select name="bowler_id">${selectOptions(players)}</select></label><p class="hint">Select a player from the bowling team. Shared players are available to both teams.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Confirm bowler</button></div></form>`,'OVER COMPLETE');
}
async function changeBatters() {
  const m=state.activeMatch; const players=await teamPlayers(m.batting_team.id);
  const dismissed=m.dismissed_player_ids||[];
  if(m.single_batter_mode) {
    showModal('Change solo batter',`<form id="batters-form" class="modal-form"><label class="field">Solo batter<select name="striker_id">${selectOptions(players,dismissed.filter(id=>Number(id)!==Number(m.striker?.id)))}</select></label><p class="hint">Only one batter occupies the crease. No non-striker or strike rotation is used.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Update batter</button></div></form>`,'SOLO BATTER');
    $('#batters-form [name=striker_id]').value=m.striker?.id||'';
    return;
  }
  showModal('Change batters',`<form id="batters-form" class="modal-form"><label class="field">Striker<select name="striker_id">${selectOptions(players,dismissed.filter(id=>Number(id)!==Number(m.striker?.id)))}</select></label><label class="field">Non-striker<select name="non_striker_id">${selectOptions(players,dismissed.filter(id=>Number(id)!==Number(m.non_striker?.id)))}</select></label><p class="hint">The two selected batters must be different and not already dismissed.</p><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Update batters</button></div></form>`,'LINE-UP');
  $('#batters-form [name=striker_id]').value=m.striker?.id||''; $('#batters-form [name=non_striker_id]').value=m.non_striker?.id||'';
}
async function beginSecondInnings() {
  const m=state.activeMatch;
  const [batters,bowlers]=await Promise.all([teamPlayers(m.bowling_team.id),teamPlayers(m.batting_team.id)]);
  showModal('Start second innings',`<form id="next-innings-form" class="modal-form"><div class="scorer-notice">${esc(m.batting_team.name)} finished on ${m.first_innings.runs}/${m.first_innings.wickets}. ${esc(m.bowling_team.name)} need ${m.first_innings.runs+1} to win.</div><label class="field">Opening striker<select name="striker_id">${selectOptions(batters)}</select></label>${m.single_batter_mode?`<div class="solo-mode-note">SINGLE-BATTER MODE CONTINUES · NO NON-STRIKER</div>`:`<label class="field">Non-striker<select name="non_striker_id">${selectOptions(batters)}</select></label>`}<label class="field">Opening bowler<select name="bowler_id">${selectOptions(bowlers)}</select></label><div class="modal-actions"><button type="button" class="btn btn-quiet" data-close-modal>Cancel</button><button class="btn btn-primary" type="submit">Start innings</button></div></form>`,'INNINGS BREAK');
}
async function swapBatters() {
  const m=state.activeMatch;
  try{state.activeMatch=await api(`/matches/${m.id}/batters`,{method:'PUT',body:JSON.stringify({striker_id:m.non_striker.id,non_striker_id:m.striker.id})});renderScorer();toast('Strike swapped.');}
  catch(error){toast(error.message,'error');}
}
async function openScorecard() {
  const data=await api(`/matches/${state.activeMatchId}/scorecard`);
  const m=state.activeMatch;
  const inningsHtml=data.innings.map((score,i)=>{const inningsTeam=i===0?(m.innings===1?m.batting_team:m.bowling_team):m.batting_team;return `<section style="margin-bottom:20px"><div class="panel-header"><div><h3>Innings ${i+1}</h3><p>${esc(inningsTeam?.name||'')}</p></div><strong>${score.runs}/${score.wickets} (${score.overs})</strong></div>${scorecardTable(score,'batting')}${scorecardTable(score,'bowling')}</section>`;}).join('');
  showModal('Full scorecard',`<div class="scorecard-export-row"><span class="hint">Create a printable PDF copy of this scorecard.</span><button class="btn btn-primary btn-small" data-action="export-scorecard-pdf">Export scorecard PDF ↗</button></div>${inningsHtml||emptyState('▤','No scorecard yet','Scorecard data will appear after deliveries are saved.')}`,'MATCH RECORD');
}

async function exportScorecardPdf(printWindow) {
  try {
    const m=state.activeMatch;
    if(!m) throw new Error('Open a match before exporting its scorecard.');
    const [data,mvpData]=await Promise.all([
      api(`/matches/${m.id}/scorecard`),
      api(`/matches/${m.id}/mvp`)
    ]);
    const inningsHtml=data.innings.map((score,i)=>{
      const team=i===0?(m.innings===1?m.batting_team:m.bowling_team):m.batting_team;
      return `<section class="innings"><div class="innings-head"><div><h2>Innings ${i+1}</h2><p>${esc(team?.name||'')}</p></div><strong>${score.runs}/${score.wickets} <small>(${esc(score.overs)} overs)</small></strong></div><h3>Batting</h3>${scorecardTable(score,'batting')}<h3>Bowling</h3>${scorecardTable(score,'bowling')}</section>`;
    }).join('');
    const mvp=mvpData.rankings?.[0];
    const title=`${esc(m.title)} — Scorecard`;
    const printable=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><style>
      @page{size:A4;margin:15mm 13mm 19mm}*{box-sizing:border-box}body{font-family:Arial,Helvetica,sans-serif;color:#19251c;margin:0;background:#fff;font-size:11px;line-height:1.45}
      .toolbar{position:sticky;top:0;background:#18251d;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;font-size:12px;z-index:5}.toolbar button{border:0;border-radius:7px;padding:9px 13px;font-weight:700;cursor:pointer}
      .document{position:relative;z-index:1;padding:22px 5px 36px}.brand{display:flex;align-items:center;gap:9px;font-weight:800;letter-spacing:2px;color:#243b29}.brand-mark{width:31px;height:31px;border:2px solid #547c3b;border-radius:8px;display:grid;place-items:center;font-size:12px;letter-spacing:0}
      h1{font-size:24px;margin:17px 0 3px} .meta{color:#617064;margin:0 0 18px}.match-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:0 0 22px}.summary-cell{background:#f4f7f1;border:1px solid #e1e8dd;border-radius:8px;padding:10px}.summary-cell small{display:block;text-transform:uppercase;letter-spacing:1px;color:#738074;font-size:8px;font-weight:700}.summary-cell strong{display:block;margin-top:3px;font-size:12px}
      .innings{break-inside:avoid;margin:0 0 25px}.innings-head{display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #294331;padding:0 0 8px;margin-bottom:12px}.innings-head h2{font-size:17px;margin:0}.innings-head p{margin:2px 0 0;color:#657166}.innings-head>strong{font-size:18px}.innings-head>strong small{font-size:10px;color:#637064}.innings h3{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;margin:15px 0 4px;color:#4e6b4c}
      .table-wrap{overflow:visible;margin:0 0 8px}.data-table{border-collapse:collapse;width:100%;font-size:9px;white-space:normal}.data-table th{text-align:left;text-transform:uppercase;letter-spacing:.8px;color:#657266;font-size:8px;padding:7px 6px;border-bottom:1px solid #cfd8cb}.data-table td{padding:7px 6px;border-bottom:1px solid #e8ede5}.data-table td strong{font-size:9px}.muted{color:#758174}.mvp-callout{border:1px solid #d9e5d2;background:#f5f9f1;border-radius:8px;padding:11px;margin-top:18px}.mvp-callout strong{font-size:12px}.mvp-callout p{margin:3px 0 0;color:#62705f;font-size:9px}
      .watermark{position:fixed;z-index:2;top:43%;left:50%;transform:translate(-50%,-50%) rotate(-31deg);font-size:70px;font-weight:900;letter-spacing:8px;color:rgba(50,86,45,.085);white-space:nowrap;pointer-events:none}.print-footer{position:fixed;bottom:-11mm;left:0;right:0;border-top:1px solid #dce4d9;padding-top:6px;text-align:center;font-size:9px;font-weight:700;letter-spacing:.4px;color:#52654f}
      @media print{.toolbar{display:none!important}.document{padding-top:0}.print-footer{position:fixed;bottom:-11mm}.watermark{position:fixed}}
      @media screen{body{max-width:850px;margin:0 auto}.document{padding:25px 35px 60px}.print-footer{position:static;margin:25px 0 12px}}
    </style></head><body><div class="toolbar"><span>AG Scorer · Scorecard PDF</span><button onclick="window.print()">Print / Save as PDF</button></div><div class="watermark">AG SCORER</div><main class="document"><div class="brand"><span class="brand-mark">AG</span><span>AG SCORER</span></div><h1>${title}</h1><p class="meta">${esc(m.venue||'Venue not set')} · ${esc(m.format)} · ${m.total_overs} overs · ${esc(statusLabel(m.status))}</p><div class="match-summary"><div class="summary-cell"><small>Team A</small><strong>${esc(m.team_a.name)}</strong></div><div class="summary-cell"><small>Team B</small><strong>${esc(m.team_b.name)}</strong></div></div>${inningsHtml}${m.result_text?`<div class="mvp-callout"><strong>Match result</strong><p>${esc(m.result_text)}</p></div>`:''}${mvp?`<div class="mvp-callout"><strong>Match MVP: ${esc(mvp.name)} · ${mvp.points} points</strong><p>${mvp.runs} runs · ${mvp.wickets} wickets · ${mvp.fours} fours · ${mvp.sixes} sixes</p></div>`:''}<footer class="print-footer">Made With Love By Amber Gupta</footer></main><script>window.addEventListener('load',()=>setTimeout(()=>window.print(),450));</script></body></html>`;
    printWindow.document.open();printWindow.document.write(printable);printWindow.document.close();
  } catch(error) {
    printWindow?.close();
    throw error;
  }
}

// Player statistics
async function showPlayerStats(id) {
  try {
    const p=await api(`/players/${id}/stats`);
    showModal(p.name,`<div class="profile-info"><span class="avatar">${esc(initials(p.name))}</span><div><strong>${esc(p.name)}</strong><small>${esc(p.role)} ${p.is_common?'· Shared player':''}</small></div></div><div class="eyebrow green">BATTING</div><div class="metric-grid" style="grid-template-columns:repeat(2,1fr);margin:10px 0 18px"><div class="metric-card"><div class="metric-top">Runs</div><div class="metric-value">${p.runs}</div></div><div class="metric-card"><div class="metric-top">Average</div><div class="metric-value">${p.batting_average}</div></div><div class="metric-card"><div class="metric-top">Strike rate</div><div class="metric-value">${p.strike_rate}</div></div><div class="metric-card"><div class="metric-top">4s / 6s</div><div class="metric-value">${p.fours} / ${p.sixes}</div></div></div><div class="eyebrow green">BOWLING</div><div class="innings-score-list" style="margin-top:9px"><div class="innings-score-row"><span>Wickets</span><strong>${p.wickets}</strong></div><div class="innings-score-row"><span>Overs</span><strong>${p.bowling_overs}</strong></div><div class="innings-score-row"><span>Runs conceded</span><strong>${p.runs_conceded}</strong></div><div class="innings-score-row"><span>Economy</span><strong>${p.economy}</strong></div></div>`,'PLAYER PROFILE');
  } catch(error){toast(error.message,'error');}
}

// Delegated actions
$('#page-content').addEventListener('click',async event=>{
  const page=event.target.closest('[data-page]'); if(page){navigate(page.dataset.page);return;}
  const target=event.target.closest('[data-action]'); if(!target)return;
  const action=target.dataset.action; const id=target.dataset.id;
  try {
    if(action==='create-match') await showCreateMatch();
    else if(action==='create-team') createTeamModal();
    else if(action==='create-player') createPlayerModal();
    else if(action==='create-common') createCommonPlayerModal();
    else if(action==='create-tournament') createTournamentModal();
    else if(action==='add-player-to-team') createPlayerModal(id);
    else if(action==='open-match') await openMatch(id);
    else if(action==='score-run') await scoreBall({runs_bat:Number(target.dataset.runs)});
    else if(action==='wicket') await chooseWicket();
    else if(action==='extra') await extraModal(target.dataset.extra);
    else if(action==='undo-ball') {state.activeMatch=await api(`/matches/${state.activeMatchId}/undo`,{method:'POST',body:'{}'});renderScorer();toast('Last delivery undone.');}
    else if(action==='swap-batters') await swapBatters();
    else if(action==='change-batters') await changeBatters();
    else if(action==='change-bowler') await chooseBowler();
    else if(action==='next-innings') await beginSecondInnings();
    else if(action==='refresh-match') {await refreshActiveMatch();toast('Score refreshed.');}
    else if(action==='scorecard-view') await openScorecard();
    else if(action==='player-stats') await showPlayerStats(id);
    else if(action==='logout') logout();
    else if(action==='open-profile') await navigate('profile');
    else if(action==='retry-page') await navigate(state.page);
  } catch(error) {toast(error.message,'error');}
});

// Modal actions (including the printable scorecard export).
$('#modal-body').addEventListener('click',async event=>{
  const target=event.target.closest('[data-action]');
  if(!target || target.dataset.action!=='export-scorecard-pdf') return;
  const printWindow=window.open('', '_blank');
  if(!printWindow){toast('Allow pop-ups for AG Scorer to export the PDF.','error');return;}
  try { await exportScorecardPdf(printWindow); }
  catch(error){toast(error.message,'error');}
});

// Modal form handling
$('#modal-body').addEventListener('submit',async event=>{
  const form=event.target; if(!form.matches('form'))return; event.preventDefault();
  const fd=new FormData(form); const data=Object.fromEntries(fd.entries());
  const button=form.querySelector('button[type=submit]'); setBusy(button,true);
  try {
    if(form.id==='create-team-form') {
      await api('/teams',{method:'POST',body:JSON.stringify({name:data.name,short_name:data.short_name})});
      closeModal();await loadCollections();toast('Team created.');await navigate('teams');
    } else if(form.id==='create-player-form') {
      await api(`/teams/${data.team_id}/players`,{method:'POST',body:JSON.stringify({name:data.name,role:data.role,jersey_number:Number(data.jersey_number||0)})});
      closeModal();await loadCollections();toast('Player added to team.');await navigate('teams');
    } else if(form.id==='create-common-form') {
      await api('/players/common',{method:'POST',body:JSON.stringify({home_team_id:Number(data.home_team_id),name:data.name,role:data.role,jersey_number:Number(data.jersey_number||0)})});
      closeModal();await loadCollections();toast('Shared player created and added to both team pickers.');await navigate('players');
    } else if(form.id==='create-tournament-form') {
      await api('/tournaments',{method:'POST',body:JSON.stringify({name:data.name,format:data.format,venue:data.venue||''})});
      closeModal();await loadCollections();toast('Tournament created.');await navigate('tournaments');
    } else if(form.id==='create-match-form') {
      const singleBatterMode=form.elements.single_batter_mode.checked;
      const payload={title:data.title,venue:data.venue||'',match_format:data.match_format,total_overs:Number(data.total_overs),team_a_id:Number(data.team_a_id),team_b_id:Number(data.team_b_id),toss_winner_id:Number(data.toss_winner_id),toss_decision:data.toss_decision,striker_id:Number(data.striker_id),non_striker_id:singleBatterMode?null:Number(data.non_striker_id),bowler_id:Number(data.bowler_id),single_batter_mode:singleBatterMode,tournament_id:data.tournament_id?Number(data.tournament_id):null};
      const match=await api('/matches',{method:'POST',body:JSON.stringify(payload)});
      closeModal();await loadCollections();toast('Match created.');await openMatch(match.id);
    } else if(form.id==='wicket-form') {
      if(!data.new_batter_id)throw new Error('Choose the incoming batter.');
      state.activeMatch=await api(`/matches/${state.activeMatchId}/balls`,{method:'POST',body:JSON.stringify({wicket_type:data.wicket_type,dismissed_player_id:Number(data.dismissed_player_id),new_batter_id:Number(data.new_batter_id)})});
      closeModal();renderScorer();
    } else if(form.id==='extra-form') {
      state.activeMatch=await api(`/matches/${state.activeMatchId}/balls`,{method:'POST',body:JSON.stringify({extra_type:data.extra_type,runs_bat:Number(data.runs_bat||0),extra_runs:Number(data.extra_runs||0),running_runs:Number(data.running_runs||0)})});
      closeModal();renderScorer();
    } else if(form.id==='bowler-form') {
      state.activeMatch=await api(`/matches/${state.activeMatchId}/bowler`,{method:'PUT',body:JSON.stringify({bowler_id:Number(data.bowler_id)})});
      closeModal();renderScorer();toast('Bowler updated.');
    } else if(form.id==='batters-form') {
      const m=state.activeMatch;
      if(!m.single_batter_mode && Number(data.striker_id)===Number(data.non_striker_id))throw new Error('Choose two different batters.');
      state.activeMatch=await api(`/matches/${state.activeMatchId}/batters`,{method:'PUT',body:JSON.stringify({striker_id:Number(data.striker_id),non_striker_id:m.single_batter_mode?null:Number(data.non_striker_id)})});
      closeModal();renderScorer();toast(m.single_batter_mode?'Solo batter updated.':'Batters updated.');
    } else if(form.id==='next-innings-form') {
      const m=state.activeMatch;
      if(!m.single_batter_mode && Number(data.striker_id)===Number(data.non_striker_id))throw new Error('Choose two different opening batters.');
      state.activeMatch=await api(`/matches/${state.activeMatchId}/next-innings`,{method:'POST',body:JSON.stringify({striker_id:Number(data.striker_id),non_striker_id:m.single_batter_mode?null:Number(data.non_striker_id),bowler_id:Number(data.bowler_id)})});
      closeModal();renderScorer();toast('Second innings started.');
    }
  } catch(error) {
    const inline=form.querySelector('.form-error'); if(inline){inline.textContent=error.message;inline.classList.remove('hidden');} else toast(error.message,'error');
  } finally {setBusy(button,false);}
});


// PWA installation prompt (shown where the browser supports it).
let deferredInstallPrompt = null;
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  deferredInstallPrompt = event;
  const button = document.getElementById('install-app-button');
  if (button) button.classList.remove('hidden');
});
window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  document.getElementById('install-app-button')?.classList.add('hidden');
  toast('AG Scorer installed.');
});
document.addEventListener('click', async event => {
  if (!event.target.closest('#install-app-button') || !deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  document.getElementById('install-app-button')?.classList.add('hidden');
});

// Boot
if(state.token) startApp(); else setAuthMode(false);
