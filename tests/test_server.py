"""Сервер целиком: HTTP-маршруты и WebSocket через TestClient."""

from fastapi.testclient import TestClient

from web.server import app


def test_pages_and_assets_are_served():
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/static/js/main.js').status_code == 200
        assert client.get('/images/pieces/wN2.png').status_code == 200
        assert client.get('/health').json()['ok'] is True


def test_two_players_over_websocket():
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as alice, client.websocket_connect('/ws') as bob:
            alice.send_json({'t': 'hello', 'id': 'ws-alice-1', 'name': 'Алиса'})
            assert alice.receive_json()['t'] == 'welcome'
            assert alice.receive_json()['t'] == 'lobby'
            bob.send_json({'t': 'hello', 'id': 'ws-bob-002', 'name': 'Борис'})
            assert bob.receive_json()['t'] == 'welcome'
            assert bob.receive_json()['t'] == 'lobby'

            alice.send_json({'t': 'create', 'color': 'w'})
            entered = alice.receive_json()
            assert entered['t'] == 'entered'
            assert alice.receive_json()['t'] == 'state'
            assert bob.receive_json()['t'] == 'lobby'          # в лобби появилась игра

            bob.send_json({'t': 'join', 'game': entered['game']})
            assert bob.receive_json()['t'] == 'entered'
            state = bob.receive_json()['game']
            assert state['you'] == 'b' and state['status'] == 'playing'

            alice.receive_json()                               # обновление после входа Бориса
            alice.send_json({'t': 'move', 'from': [5, 2], 'to': [5, 5]})
            for ws in (alice, bob):
                msg = ws.receive_json()
                assert msg['t'] == 'state' and msg['game']['turn'] == 'b'

            alice.send_text('not json')                        # мусор игнорируется
            alice.send_json({'t': 'resign'})
            assert alice.receive_json()['game']['result'] == 'resign'
