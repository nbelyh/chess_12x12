"""Лобби и комнаты онлайн-игры, без привязки к WebSocket.

Hub получает сообщения от подключений (dict из JSON) и рассылает ответы через
Connection.send. Сервер (web/server.py) лишь переносит JSON между сокетом и Hub,
поэтому всю логику можно проверять в тестах без сети.
"""

import random
import string
import time

from core.board import other
from core.game import Game, MoveError

NAME_MAX = 24
ROOM_ID_ALPHABET = string.ascii_lowercase + string.digits
ROOM_ID_LEN = 6
# Через сколько секунд без подключённых зрителей удалять комнату.
IDLE_WAITING = 10 * 60
IDLE_OVER = 10 * 60
IDLE_PLAYING = 2 * 60 * 60


class Connection:
    """Одно подключение браузера. send переопределяется сервером или тестом."""

    def __init__(self, send):
        self._send = send
        self.client_id = None
        self.name = None
        self.room = None

    async def send(self, msg):
        await self._send(msg)


class Room:
    def __init__(self, room_id):
        self.id = room_id
        self.game = Game()
        self.seats = {'w': None, 'b': None}     # client_id игрока
        self.names = {}                         # client_id -> имя
        self.conns = set()
        self.takeback_by = None                 # кто попросил вернуть ход
        self.touched = time.monotonic()

    def color_of(self, client_id):
        for color, cid in self.seats.items():
            if cid is not None and cid == client_id:
                return color
        return None

    def online(self, color):
        cid = self.seats[color]
        return cid is not None and any(c.client_id == cid for c in self.conns)

    @property
    def status(self):
        if self.game.over:
            return 'over'
        if None in self.seats.values():
            return 'waiting'
        return 'playing'

    def player_info(self, color):
        cid = self.seats[color]
        if cid is None:
            return None
        return {'name': self.names.get(cid, '?'), 'online': self.online(color)}

    def summary(self):
        return {
            'id': self.id,
            'status': self.status,
            'players': {c: self.player_info(c) for c in ('w', 'b')},
            'watchers': sum(1 for c in self.conns if self.color_of(c.client_id) is None),
            'moves': len(self.game.history),
        }

    def state_for(self, conn):
        you = self.color_of(conn.client_id)
        state = self.summary()
        state.update(self.game.to_dict(you))
        state['you'] = you
        state['takeback'] = self.takeback_by
        return state


class Hub:
    def __init__(self, rng=None):
        self.conns = set()
        self.rooms = {}
        self.names = {}         # client_id -> имя (запоминаем между подключениями)
        self.rng = rng or random.SystemRandom()

    # --- Подключения ---

    async def connect(self, conn):
        self.conns.add(conn)

    async def disconnect(self, conn):
        self.conns.discard(conn)
        room = conn.room
        if room is not None:
            room.conns.discard(conn)
            room.touched = time.monotonic()
            await self.broadcast_room(room)
        await self.broadcast_lobby()

    async def handle(self, conn, msg):
        if not isinstance(msg, dict):
            return
        kind = msg.get('t')
        if kind != 'hello' and conn.client_id is None:
            await conn.send({'t': 'error', 'msg': 'Сначала представьтесь'})
            return
        handler = getattr(self, f'on_{kind}', None) if isinstance(kind, str) else None
        if handler is None:
            await conn.send({'t': 'error', 'msg': 'Неизвестная команда'})
            return
        try:
            await handler(conn, msg)
        except MoveError as e:
            await conn.send({'t': 'error', 'msg': str(e)})

    # --- Лобби ---

    async def on_hello(self, conn, msg):
        client_id = str(msg.get('id') or '')[:64]
        if len(client_id) < 8:
            await conn.send({'t': 'error', 'msg': 'Некорректный идентификатор'})
            return
        conn.client_id = client_id
        name = clean_name(msg.get('name')) or self.names.get(client_id)
        if name:
            self.set_name(conn, name)
        await conn.send({'t': 'welcome', 'name': conn.name})
        await self.send_lobby(conn)

    async def on_name(self, conn, msg):
        name = clean_name(msg.get('name'))
        if not name:
            raise MoveError("Введите имя")
        self.set_name(conn, name)
        await conn.send({'t': 'welcome', 'name': conn.name})
        if conn.room is not None:
            await self.broadcast_room(conn.room)
        await self.broadcast_lobby()

    def set_name(self, conn, name):
        conn.name = name
        self.names[conn.client_id] = name
        for room in self.rooms.values():
            if conn.client_id in room.names:
                room.names[conn.client_id] = name

    async def on_create(self, conn, msg):
        if not conn.name:
            raise MoveError("Введите имя")
        color = msg.get('color')
        if color not in ('w', 'b'):
            color = self.rng.choice(['w', 'b'])
        room = Room(self.new_room_id())
        self.rooms[room.id] = room
        room.seats[color] = conn.client_id
        room.names[conn.client_id] = conn.name
        await self.enter(conn, room)

    async def on_join(self, conn, msg):
        room = self.rooms.get(str(msg.get('game') or ''))
        if room is None:
            await conn.send({'t': 'gone', 'msg': 'Игра не найдена — возможно, она уже завершилась'})
            return
        if room.color_of(conn.client_id) is None and room.status == 'waiting' and conn.name:
            free = 'w' if room.seats['w'] is None else 'b'
            room.seats[free] = conn.client_id
            room.names[conn.client_id] = conn.name
        await self.enter(conn, room)

    async def on_leave(self, conn, msg):
        room = conn.room
        if room is None:
            return
        room.conns.discard(conn)
        conn.room = None
        # Создатель ушёл, так и не дождавшись соперника — игра больше не нужна.
        if room.status == 'waiting' and room.game.history == [] and not room.conns:
            self.rooms.pop(room.id, None)
        else:
            await self.broadcast_room(room)
        await self.send_lobby(conn)
        await self.broadcast_lobby()

    async def enter(self, conn, room):
        if conn.room is not None and conn.room is not room:
            old = conn.room
            old.conns.discard(conn)
            await self.broadcast_room(old)
        conn.room = room
        room.conns.add(conn)
        room.touched = time.monotonic()
        await conn.send({'t': 'entered', 'game': room.id})
        await self.broadcast_room(room)
        await self.broadcast_lobby()

    # --- Ходы и кнопки ---

    def player(self, conn):
        room = conn.room
        if room is None:
            raise MoveError("Вы не в игре")
        color = room.color_of(conn.client_id)
        if color is None:
            raise MoveError("Вы зритель")
        return room, color

    async def on_move(self, conn, msg):
        room, color = self.player(conn)
        if room.status == 'waiting':
            raise MoveError("Ждём соперника")
        room.game.move(color, parse_square(msg.get('from')), parse_square(msg.get('to')))
        room.takeback_by = None
        await self.after_change(room)

    async def on_promote(self, conn, msg):
        room, color = self.player(conn)
        room.game.promote(color, msg.get('piece'))
        await self.after_change(room)

    async def on_resign(self, conn, msg):
        room, color = self.player(conn)
        room.game.resign(color)
        room.takeback_by = None
        await self.after_change(room)

    async def on_draw(self, conn, msg):
        room, color = self.player(conn)
        if room.status == 'waiting':
            raise MoveError("Ждём соперника")
        room.game.toggle_draw(color)
        await self.after_change(room)

    async def on_takeback(self, conn, msg):
        room, color = self.player(conn)
        if room.game.over or not room.game.history:
            raise MoveError("Нечего возвращать")
        if room.takeback_by == other(color):
            # Встречная просьба — считаем согласием.
            room.game.undo()
            room.takeback_by = None
        else:
            room.takeback_by = color
        await self.after_change(room)

    async def on_takeback_reply(self, conn, msg):
        room, color = self.player(conn)
        if room.takeback_by != other(color):
            raise MoveError("Нет запроса на возврат хода")
        room.takeback_by = None
        if msg.get('accept'):
            room.game.undo()
        await self.after_change(room)

    async def after_change(self, room):
        room.touched = time.monotonic()
        await self.broadcast_room(room)
        await self.broadcast_lobby()

    # --- Рассылка ---

    def lobby(self):
        games = [r.summary() for r in self.rooms.values() if r.status != 'over']
        games.sort(key=lambda g: (g['status'] != 'waiting', g['id']))
        return {'t': 'lobby', 'games': games, 'online': len({c.client_id for c in self.conns if c.client_id})}

    async def send_lobby(self, conn):
        await conn.send(self.lobby())

    async def broadcast_lobby(self):
        msg = self.lobby()
        for conn in list(self.conns):
            if conn.room is None and conn.client_id is not None:
                await safe_send(conn, msg)

    async def broadcast_room(self, room):
        for conn in list(room.conns):
            await safe_send(conn, {'t': 'state', 'game': room.state_for(conn)})

    # --- Обслуживание ---

    def new_room_id(self):
        while True:
            room_id = ''.join(self.rng.choice(ROOM_ID_ALPHABET) for _ in range(ROOM_ID_LEN))
            if room_id not in self.rooms:
                return room_id

    def collect_garbage(self, now=None):
        """Удалить комнаты, в которых давно никого нет. Возвращает число удалённых."""
        now = time.monotonic() if now is None else now
        removed = 0
        for room_id, room in list(self.rooms.items()):
            if room.conns:
                continue
            limit = {'waiting': IDLE_WAITING, 'over': IDLE_OVER}.get(room.status, IDLE_PLAYING)
            if now - room.touched > limit:
                del self.rooms[room_id]
                removed += 1
        return removed


async def safe_send(conn, msg):
    try:
        await conn.send(msg)
    except Exception:
        # Сокет уже закрыт — disconnect() уберёт его.
        pass


def clean_name(name):
    if not isinstance(name, str):
        return None
    name = ' '.join(name.split())[:NAME_MAX]
    return name or None


def parse_square(value):
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 12 for v in value)):
        return (value[0], value[1])
    raise MoveError("Некорректное поле")
