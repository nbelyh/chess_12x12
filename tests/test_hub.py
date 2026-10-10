"""Лобби и комнаты (web.hub) без сети: подключения — заглушки, собирающие сообщения."""

import asyncio
import random

import pytest

from web.hub import Connection, Hub


class Client:
    def __init__(self, hub, client_id, name):
        self.hub = hub
        self.inbox = []

        async def send(msg):
            self.inbox.append(msg)

        self.conn = Connection(send)
        self.id = client_id
        self.name = name

    def do(self, **msg):
        asyncio.run(self.hub.handle(self.conn, msg))
        return self

    def connect(self):
        asyncio.run(self.hub.connect(self.conn))
        return self.do(t='hello', id=self.id, name=self.name)

    def disconnect(self):
        asyncio.run(self.hub.disconnect(self.conn))

    def last(self, kind):
        for msg in reversed(self.inbox):
            if msg['t'] == kind:
                return msg
        raise AssertionError(f'нет сообщения {kind}: {self.inbox}')

    @property
    def state(self):
        return self.last('state')['game']


@pytest.fixture
def hub():
    return Hub(rng=random.Random(0))


def start_game(hub):
    alice = Client(hub, 'alice-0001', 'Алиса').connect()
    bob = Client(hub, 'bob-000002', 'Борис').connect()
    alice.do(t='create', color='w')
    game_id = alice.last('entered')['game']
    bob.do(t='join', game=game_id)
    return alice, bob, game_id


def test_hello_requires_id_and_returns_lobby(hub):
    c = Client(hub, 'short', 'X')
    asyncio.run(hub.connect(c.conn))
    c.do(t='hello', id='short')
    assert c.last('error')
    c.do(t='create')
    assert c.last('error')['msg'] == 'Сначала представьтесь'

    c = Client(hub, 'client-123', 'Иван').connect()
    assert c.last('welcome')['name'] == 'Иван'
    assert c.last('lobby')['games'] == []


def test_create_and_join_seats_both_players(hub):
    alice, bob, game_id = start_game(hub)
    assert alice.state['you'] == 'w' and bob.state['you'] == 'b'
    assert alice.state['status'] == 'playing'
    assert alice.state['players']['b']['name'] == 'Борис'
    assert bob.last('entered')['game'] == game_id


def test_third_visitor_watches(hub):
    alice, bob, game_id = start_game(hub)
    carl = Client(hub, 'carl-00003', 'Карл').connect().do(t='join', game=game_id)
    assert carl.state['you'] is None
    assert carl.state['legal'] == {}
    assert alice.state['watchers'] == 1
    carl.do(t='move', **{'from': [5, 2], 'to': [5, 5]})
    assert carl.last('error')['msg'] == 'Вы зритель'


def test_moves_are_broadcast_and_validated(hub):
    alice, bob, _ = start_game(hub)
    bob.do(t='move', **{'from': [5, 9], 'to': [5, 8]})
    assert bob.last('error')['msg'] == 'Сейчас не ваш ход'
    alice.do(t='move', **{'from': [5, 2], 'to': [5, 5]})
    assert bob.state['turn'] == 'b' and bob.state['legal']
    assert [5, 5, 'w', 'P'] in bob.state['board']
    alice.do(t='move', **{'from': 'junk', 'to': [1, 2]})
    assert alice.last('error')['msg'] == 'Некорректное поле'


def test_cannot_move_before_opponent_joins(hub):
    alice = Client(hub, 'alice-0001', 'Алиса').connect().do(t='create', color='w')
    alice.do(t='move', **{'from': [5, 2], 'to': [5, 5]})
    assert alice.last('error')['msg'] == 'Ждём соперника'


def test_takeback_needs_opponent_consent(hub):
    alice, bob, _ = start_game(hub)
    alice.do(t='move', **{'from': [5, 2], 'to': [5, 5]})
    alice.do(t='takeback')
    assert bob.state['takeback'] == 'w'
    bob.do(t='takeback_reply', accept=False)
    assert alice.state['takeback'] is None and alice.state['moves'] == 1

    alice.do(t='takeback')
    bob.do(t='takeback_reply', accept=True)
    assert alice.state['moves'] == 0 and alice.state['turn'] == 'w'


def test_draw_and_resign(hub):
    alice, bob, _ = start_game(hub)
    alice.do(t='draw')
    assert bob.state['drawVotes'] == {'w': True, 'b': False}
    bob.do(t='draw')
    assert alice.state['result'] == 'draw'

    alice, bob, _ = start_game(hub)
    bob.do(t='resign')
    assert alice.state['result'] == 'resign' and alice.state['winner'] == 'w'


def test_reconnect_keeps_seat(hub):
    alice, bob, game_id = start_game(hub)
    bob.disconnect()
    assert alice.state['players']['b']['online'] is False
    bob2 = Client(hub, 'bob-000002', None).connect()
    assert bob2.last('welcome')['name'] == 'Борис'      # имя запомнено сервером
    bob2.do(t='join', game=game_id)
    assert bob2.state['you'] == 'b'
    assert alice.state['players']['b']['online'] is True


def test_lobby_lists_open_games_and_leaving_empty_game_removes_it(hub):
    alice = Client(hub, 'alice-0001', 'Алиса').connect().do(t='create', color='b')
    watcher = Client(hub, 'watch-0004', 'Вера').connect()
    games = watcher.last('lobby')['games']
    assert len(games) == 1 and games[0]['status'] == 'waiting'
    assert games[0]['players']['b']['name'] == 'Алиса'

    alice.do(t='leave')
    assert watcher.last('lobby')['games'] == []
    assert hub.rooms == {}


def test_unknown_game(hub):
    c = Client(hub, 'client-123', 'Иван').connect().do(t='join', game='nope')
    assert c.last('gone')


def test_rename_updates_room(hub):
    alice, bob, _ = start_game(hub)
    alice.do(t='name', name='  Алиса   Петровна ')
    assert bob.state['players']['w']['name'] == 'Алиса Петровна'


def test_garbage_collection_removes_abandoned_rooms(hub):
    alice, bob, _ = start_game(hub)
    alice.disconnect()
    bob.disconnect()
    room = next(iter(hub.rooms.values()))
    assert hub.collect_garbage(now=room.touched + 60) == 0
    assert hub.collect_garbage(now=room.touched + 3 * 60 * 60) == 1
    assert hub.rooms == {}
