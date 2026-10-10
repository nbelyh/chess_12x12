// Доска: отрисовка позиции, подсказки ходов, перетаскивание и ход кликом.

const SIZE = 12;
const FILES = 'abcdefghijkl';
const key = (c, r) => `${c},${r}`;

export function pieceSrc(color, type) {
  return `/images/pieces/${color}${type}.png`;
}

export class Board {
  constructor(el, { onMove, onSelect }) {
    this.el = el;
    this.onMove = onMove;
    this.onSelect = onSelect;
    this.pieces = new Map();   // "c,r" -> [color, type]
    this.legal = {};           // "c,r" -> [[tc, tr, kind], ...]
    this.lastMove = null;
    this.check = [];
    this.flipped = false;
    this.selected = null;      // "c,r"
    this.drag = null;
    el.addEventListener('pointerdown', (e) => this.pointerDown(e));
    el.addEventListener('pointermove', (e) => this.pointerMove(e));
    el.addEventListener('pointerup', (e) => this.pointerUp(e));
    el.addEventListener('pointercancel', () => this.cancelDrag());
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  setState({ board, legal, lastMove, check }) {
    this.pieces = new Map(board.map(([c, r, color, type]) => [key(c, r), [color, type]]));
    this.legal = legal || {};
    this.lastMove = lastMove;
    this.check = check || [];
    if (this.selected && !this.legal[this.selected]) this.selected = null;
    this.render();
  }

  setFlipped(flipped) {
    this.flipped = flipped;
    this.render();
  }

  // Показать ход сразу, не дожидаясь ответа сервера.
  applyLocal(from, to, target) {
    const a = key(...from), b = key(...to);
    const moving = this.pieces.get(a);
    const kind = target[2];
    if (kind === 'castle') {
      this.pieces.set(a, this.pieces.get(b));
      this.pieces.set(b, moving);
    } else {
      if (kind === 'ep') this.pieces.delete(key(...target[3]));
      this.pieces.delete(a);
      this.pieces.set(b, moving);
    }
    this.legal = {};
    this.selected = null;
    this.lastMove = [from, to];
    this.check = [];
    this.render();
  }

  // --- Геометрия ---

  toScreen(c, r) {
    return this.flipped ? [SIZE - 1 - c, r] : [c, SIZE - 1 - r];   // [колонка, строка] на экране
  }

  squareAt(clientX, clientY) {
    const rect = this.el.getBoundingClientRect();
    const x = Math.floor(((clientX - rect.left) / rect.width) * SIZE);
    const y = Math.floor(((clientY - rect.top) / rect.height) * SIZE);
    if (x < 0 || y < 0 || x >= SIZE || y >= SIZE) return null;
    return this.flipped ? [SIZE - 1 - x, y] : [x, SIZE - 1 - y];
  }

  place(node, c, r) {
    const [x, y] = this.toScreen(c, r);
    node.style.left = `${(x * 100) / SIZE}%`;
    node.style.top = `${(y * 100) / SIZE}%`;
  }

  // --- Отрисовка ---

  targets() {
    if (!this.selected) return new Map();
    return new Map((this.legal[this.selected] || []).map((t) => [key(t[0], t[1]), t]));
  }

  render() {
    if (this.selected !== this.reported) {
      this.reported = this.selected;
      this.onSelect(this.selected ? this.pieces.get(this.selected) : null);
    }
    const frag = document.createDocumentFragment();
    const targets = this.targets();
    const last = new Set(this.lastMove ? this.lastMove.map(([c, r]) => key(c, r)) : []);
    const checks = new Set(this.check.map(([c, r]) => key(c, r)));
    const bottomRow = this.flipped ? SIZE - 1 : 0;
    const leftCol = this.flipped ? SIZE - 1 : 0;

    for (let c = 0; c < SIZE; c++) {
      for (let r = 0; r < SIZE; r++) {
        const k = key(c, r);
        const sq = document.createElement('div');
        sq.className = `sq ${(c + r) % 2 === 0 ? 'light' : 'dark'}`;   // как в настольной версии: a1 светлое
        if (last.has(k)) sq.classList.add('last');
        if (checks.has(k)) sq.classList.add('check');
        if (k === this.selected) sq.classList.add('selected');
        if (r === bottomRow) sq.append(coord('file', FILES[c]));
        if (c === leftCol) sq.append(coord('rank', r + 1));
        this.place(sq, c, r);
        frag.append(sq);

        const target = targets.get(k);
        if (target) {
          const mark = document.createElement('div');
          mark.className = `mark ${target[2]}`;
          sq.append(mark);
        }
      }
    }
    for (const [k, [color, type]] of this.pieces) {
      const [c, r] = k.split(',').map(Number);
      const p = document.createElement('div');
      p.className = `piece ${color} ${type}`;
      if (this.drag && this.drag.from === k) p.classList.add('dragging');
      p.dataset.key = k;
      const img = document.createElement('img');
      img.src = pieceSrc(color, type);
      img.alt = '';
      img.draggable = false;
      p.append(img);
      this.place(p, c, r);
      frag.append(p);
    }
    this.el.replaceChildren(frag);
  }

  // --- Ввод ---

  pointerDown(e) {
    if (e.button !== 0) return;
    const sq = this.squareAt(e.clientX, e.clientY);
    if (!sq) return;
    const k = key(...sq);
    const target = this.targets().get(k);
    if (target) {
      this.commit(this.selected, sq, target);
      return;
    }
    if (!this.legal[k]) {
      if (this.selected) {
        this.selected = null;
        this.render();
      }
      return;
    }
    this.selected = k;
    const [color, type] = this.pieces.get(k);
    const ghost = document.createElement('div');
    const cell = this.el.getBoundingClientRect().width / SIZE;
    ghost.className = `ghost-piece ${color} ${type}`;
    ghost.style.width = ghost.style.height = `${cell}px`;
    ghost.innerHTML = `<img src="${pieceSrc(color, type)}" alt="">`;
    ghost.style.left = `${e.clientX}px`;
    ghost.style.top = `${e.clientY}px`;
    ghost.hidden = true;
    document.body.append(ghost);
    this.drag = { from: k, ghost, x: e.clientX, y: e.clientY, moved: false };
    try { this.el.setPointerCapture(e.pointerId); } catch { /* синтетические события */ }
    this.render();
  }

  pointerMove(e) {
    const d = this.drag;
    if (!d) return;
    if (!d.moved && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4) {
      d.moved = true;
      d.ghost.hidden = false;
      this.render();
    }
    d.ghost.style.left = `${e.clientX}px`;
    d.ghost.style.top = `${e.clientY}px`;
  }

  pointerUp(e) {
    const d = this.drag;
    if (!d) return;
    this.cancelDrag();
    if (!d.moved) return;            // обычный клик: фигура остаётся выбранной
    const sq = this.squareAt(e.clientX, e.clientY);
    const target = sq && this.targets().get(key(...sq));
    if (target) {
      this.commit(d.from, sq, target);
    } else {
      this.render();
    }
  }

  cancelDrag() {
    if (!this.drag) return;
    this.drag.ghost.remove();
    this.drag = null;
    this.render();
  }

  commit(fromKey, to, target) {
    const from = fromKey.split(',').map(Number);
    this.applyLocal(from, to, target);
    this.onMove(from, to);
  }
}

function coord(cls, text) {
  const span = document.createElement('span');
  span.className = `coord ${cls}`;
  span.textContent = text;
  return span;
}
