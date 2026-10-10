// Приложение: имя, лобби, партия. Сервер — источник истины, страница только показывает состояние.

import { Board, pieceSrc } from './board.js';
import { Net } from './net.js';
import { PIECES, PIECE_INFO } from './pieces.js';

const $ = (id) => document.getElementById(id);
const LABEL = { w: 'Белые', b: 'Чёрные' };
const LABEL_GEN = { w: 'белых', b: 'чёрных' };
const PROMO = [['Q', 'Ферзь'], ['R', 'Ладья'], ['B', 'Слон'], ['N', 'Конь']];

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* приватный режим */ } },
};

function clientId() {
  let id = store.get('chess12.id');
  if (!id) {
    id = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now());
    store.set('chess12.id', id);
  }
  return id;
}

const app = {
  id: clientId(),
  name: store.get('chess12.name'),
  gameId: new URLSearchParams(location.search).get('g'),
  game: null,
  localFlip: false,
  resultDismissed: false,
  resignArmed: null,
};

const net = new Net({
  onOpen: () => net.send({ t: 'hello', id: app.id, name: app.name }),
  onMessage: handle,
  onStatus: (ok) => { $('conn').hidden = ok; },
});

const board = new Board($('board'), {
  onMove: (from, to) => net.send({ t: 'move', from, to }),
  onSelect: (piece) => showHint(piece),
});

// --- Сообщения сервера ---

function handle(msg) {
  switch (msg.t) {
    case 'welcome':
      app.name = msg.name;
      renderMe();
      if (!app.name) return show('name-screen');
      if (app.gameId) net.send({ t: 'join', game: app.gameId });
      else show('lobby');
      break;
    case 'lobby':
      renderLobby(msg);
      break;
    case 'entered':
      if (app.gameId !== msg.game) {
        app.gameId = msg.game;
        history.pushState(null, '', `/?g=${msg.game}`);
      }
      break;
    case 'state':
      onState(msg.game);
      break;
    case 'gone':
      toast(msg.msg);
      goLobby();
      break;
    case 'error':
      toast(msg.msg);
      if (app.game) board.setState(app.game);   // откатить показанный заранее ход
      break;
  }
}

// --- Экраны ---

function show(id) {
  for (const s of ['name-screen', 'lobby', 'game']) $(s).hidden = s !== id;
}

function renderMe() {
  const me = $('me');
  me.replaceChildren();
  if (!app.name) return;
  me.append(app.name);
  const btn = document.createElement('button');
  btn.textContent = 'изменить';
  btn.onclick = () => {
    $('name-input').value = app.name;
    show('name-screen');
    $('name-input').focus();
  };
  me.append(btn);
}

$('name-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = $('name-input').value.trim();
  if (!name) return;
  store.set('chess12.name', name);
  net.send({ t: 'name', name });
  if (app.gameId) net.send({ t: 'join', game: app.gameId });
  else show('lobby');
});

// --- Лобби ---

let chosenColor = 'random';
for (const btn of $('color-choice').querySelectorAll('button')) {
  btn.addEventListener('click', () => {
    chosenColor = btn.dataset.color;
    for (const b of $('color-choice').querySelectorAll('button')) b.classList.toggle('on', b === btn);
  });
}
$('create-btn').addEventListener('click', () => net.send({ t: 'create', color: chosenColor }));

function renderLobby({ games, online }) {
  $('online').textContent = `· онлайн: ${online}`;
  $('no-games').hidden = games.length > 0;
  $('games').replaceChildren(...games.map((g) => {
    const li = document.createElement('li');
    const who = document.createElement('div');
    who.className = 'who';
    who.append(playerLabel('w', g.players.w), '  —  ', playerLabel('b', g.players.b));
    const tag = document.createElement('span');
    tag.className = `tag ${g.status}`;
    tag.textContent = g.status === 'waiting' ? 'ждёт соперника' : `идёт · ход ${Math.floor(g.moves / 2) + 1}`;
    const btn = document.createElement('button');
    btn.className = g.status === 'waiting' ? 'primary' : 'ghost';
    btn.textContent = g.status === 'waiting' ? 'Играть' : 'Смотреть';
    btn.onclick = () => openGame(g.id);
    li.append(who, tag, btn);
    return li;
  }));
}

function playerLabel(color, p) {
  const span = document.createElement('span');
  const sw = document.createElement('span');
  sw.className = `swatch ${color}`;
  span.append(sw, p ? p.name : '…');
  if (p) {
    const dot = document.createElement('span');
    dot.className = `dot ${p.online ? 'on' : ''}`;
    span.append(dot);
  }
  return span;
}

function openGame(id) {
  net.send({ t: 'join', game: id });
}

function goLobby() {
  if (app.gameId) net.send({ t: 'leave' });
  app.gameId = null;
  app.game = null;
  if (location.search) history.pushState(null, '', '/');
  show(app.name ? 'lobby' : 'name-screen');
}

window.addEventListener('popstate', () => {
  const id = new URLSearchParams(location.search).get('g');
  if (id) {
    app.gameId = id;
    net.send({ t: 'join', game: id });
  } else {
    goLobby();
  }
});
$('brand').addEventListener('click', (e) => { e.preventDefault(); goLobby(); });
$('to-lobby').addEventListener('click', goLobby);

// --- Партия ---

function onState(g) {
  if (g.id !== app.gameId) return;   // устаревшее сообщение после выхода
  const isNew = !app.game || app.game.id !== g.id;
  if (isNew) {
    app.localFlip = false;
    app.resultDismissed = false;
  }
  if (!g.result) app.resultDismissed = false;
  app.game = g;
  show('game');
  board.flipped = (g.you === 'b') !== app.localFlip;
  board.setState(g);
  renderPlayers(g);
  renderStatus(g);
  renderControls(g);
  renderOverlay(g);
  renderRequest(g);
}

function renderPlayers(g) {
  const bottom = board.flipped ? 'b' : 'w';
  fillPlayer($('player-bottom'), bottom, g);
  fillPlayer($('player-top'), bottom === 'w' ? 'b' : 'w', g);
}

function fillPlayer(el, color, g) {
  const p = g.players[color];
  el.replaceChildren();
  const sw = document.createElement('span');
  sw.className = `swatch ${color}`;
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = p ? p.name : 'ждём соперника…';
  el.append(sw, name);
  if (p) {
    const dot = document.createElement('span');
    dot.className = `dot ${p.online ? 'on' : ''}`;
    dot.title = p.online ? 'в сети' : 'не в сети';
    el.append(dot);
  }
  if (g.you === color) el.append(muted(' (вы)'));
  if (g.drawVotes[color] && !g.result) el.append(badge('предлагает ничью'));
  if (g.takeback === color) el.append(badge('просит вернуть ход'));
  if (!g.result && g.status === 'playing' && g.turn === color) {
    const t = document.createElement('span');
    t.className = 'turn';
    t.textContent = 'ходит';
    el.append(t);
  }
}

function renderStatus(g) {
  let text;
  if (g.result) text = 'Партия окончена';
  else if (g.status === 'waiting') text = 'Ждём соперника — отправьте ему ссылку';
  else if (!g.you) text = `Вы смотрите партию · ход ${LABEL_GEN[g.turn]}`;
  else if (g.promotion) text = g.promotion[2] === g.you ? 'Выберите фигуру' : 'Соперник выбирает фигуру…';
  else text = g.turn === g.you ? (g.check.length ? 'Вам шах! Ваш ход' : 'Ваш ход') : 'Ход соперника';
  $('status').textContent = text;
}

function renderControls(g) {
  const playing = !!g.you && !g.result;
  const started = g.status === 'playing';
  $('controls').querySelectorAll('.ctrl').forEach((b) => b.classList.remove('active', 'confirm'));
  $('btn-resign').hidden = $('btn-draw').hidden = $('btn-takeback').hidden = !g.you;

  $('btn-resign').disabled = !playing;
  $('btn-resign').querySelector('span').textContent = 'Сдаться';
  app.resignArmed = null;

  const draw = $('btn-draw');
  draw.disabled = !playing || !started;
  const opp = g.you === 'w' ? 'b' : 'w';
  let drawLabel = 'Ничья';
  if (g.you && g.drawVotes[g.you]) { drawLabel = 'Отменить ничью'; draw.classList.add('active'); }
  else if (g.you && g.drawVotes[opp]) { drawLabel = 'Принять ничью'; draw.classList.add('active'); }
  draw.querySelector('span').textContent = drawLabel;

  const tb = $('btn-takeback');
  tb.disabled = !playing || !started || g.moves === 0 || g.takeback === g.you;
  tb.querySelector('span').textContent = g.takeback === g.you ? 'Запрос отправлен' : 'Вернуть ход';
}

$('btn-resign').addEventListener('click', () => {
  const btn = $('btn-resign');
  if (app.resignArmed) {
    clearTimeout(app.resignArmed);
    app.resignArmed = null;
    net.send({ t: 'resign' });
    return;
  }
  btn.classList.add('confirm');
  btn.querySelector('span').textContent = 'Точно?';
  app.resignArmed = setTimeout(() => {
    app.resignArmed = null;
    btn.classList.remove('confirm');
    btn.querySelector('span').textContent = 'Сдаться';
  }, 3000);
});
$('btn-draw').addEventListener('click', () => net.send({ t: 'draw' }));
$('btn-takeback').addEventListener('click', () => net.send({ t: 'takeback' }));
$('btn-flip').addEventListener('click', () => {
  app.localFlip = !app.localFlip;
  if (app.game) onState(app.game);
});
$('copy-link').addEventListener('click', async () => {
  const url = `${location.origin}/?g=${app.gameId}`;
  try {
    await navigator.clipboard.writeText(url);
    toast('Ссылка скопирована');
  } catch {
    prompt('Ссылка на игру:', url);
  }
});

function renderOverlay(g) {
  const ov = $('overlay');
  ov.replaceChildren();
  ov.hidden = true;
  if (g.result && !app.resultDismissed) {
    ov.append(resultBox(g));
    ov.hidden = false;
  } else if (!g.result && g.promotion && g.promotion[2] === g.you) {
    ov.append(promotionBox(g.you));
    ov.hidden = false;
  }
}

function resultBox(g) {
  const box = div('box');
  const title = div('title');
  const sub = div('sub');
  if (g.result === 'mate') {
    title.className += ' win';
    title.textContent = `Мат! Победа ${LABEL_GEN[g.winner]}!`;
  } else if (g.result === 'resign') {
    title.className += ' resign';
    title.textContent = `${LABEL[g.resignedBy]} сдались!`;
    sub.textContent = `Победа ${LABEL_GEN[g.winner]}`;
  } else {
    title.className += ' draw';
    title.textContent = 'НИЧЬЯ';
    if (g.result === 'stalemate') sub.textContent = 'Пат — ходить некуда';
  }
  if (g.you && g.winner) sub.textContent = g.winner === g.you ? 'Вы выиграли 🎉' : 'Вы проиграли';
  const actions = div('actions');
  actions.append(
    button('Посмотреть доску', 'ghost', () => { app.resultDismissed = true; renderOverlay(g); }),
    button('В лобби', 'primary', goLobby),
  );
  box.append(title, sub, actions);
  return box;
}

function promotionBox(color) {
  const box = div('box');
  const title = div('title');
  title.textContent = 'Превращение';
  title.style.fontSize = '22px';
  const row = div('promo');
  for (const [type, label] of PROMO) {
    const b = document.createElement('button');
    b.innerHTML = `<img src="${pieceSrc(color, type)}" alt=""><span>${label}</span>`;
    b.onclick = () => net.send({ t: 'promote', piece: type });
    row.append(b);
  }
  box.append(title, row);
  return box;
}

function renderRequest(g) {
  const el = $('request');
  el.replaceChildren();
  const opp = g.you === 'w' ? 'b' : 'w';
  el.hidden = !(g.you && !g.result && g.takeback === opp);
  if (el.hidden) return;
  const text = document.createElement('span');
  text.textContent = 'Соперник просит вернуть последний ход';
  el.append(
    text,
    button('Разрешить', 'primary', () => net.send({ t: 'takeback_reply', accept: true })),
    button('Отказать', 'ghost', () => net.send({ t: 'takeback_reply', accept: false })),
  );
}

// --- Правила и подсказки ---

function showHint(piece) {
  const hint = $('hint');
  if (!piece) {
    hint.replaceChildren();
    return;
  }
  const [color, type] = piece;
  const info = PIECE_INFO[type];
  const img = document.createElement('img');
  img.src = pieceSrc(color, type);
  img.alt = '';
  const b = document.createElement('b');
  b.textContent = `${info.name}. `;
  hint.replaceChildren(img, b, info.text);
}

$('rules-pieces').replaceChildren(...PIECES.map(([type, name, text]) => {
  const li = document.createElement('li');
  const tile = document.createElement('span');
  tile.className = `tile ${type}`;
  const img = document.createElement('img');
  img.src = pieceSrc('w', type);
  img.alt = '';
  tile.append(img);
  const body = document.createElement('div');
  const b = document.createElement('b');
  b.textContent = name;
  body.append(b, document.createElement('br'), text);
  li.append(tile, body);
  return li;
}));
$('rules-btn').addEventListener('click', () => $('rules').showModal());
$('rules-close').addEventListener('click', () => $('rules').close());
$('rules').addEventListener('click', (e) => { if (e.target === $('rules')) $('rules').close(); });

// --- Мелочи ---

function div(cls) {
  const d = document.createElement('div');
  d.className = cls;
  return d;
}

function button(text, cls, onclick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = cls;
  b.textContent = text;
  b.onclick = onclick;
  return b;
}

function badge(text) {
  const s = document.createElement('span');
  s.className = 'badge';
  s.textContent = text;
  return s;
}

function muted(text) {
  const s = document.createElement('span');
  s.className = 'muted';
  s.textContent = text;
  return s;
}

let toastTimer = null;
function toast(text) {
  const t = $('toast');
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3000);
}

net.connect();
