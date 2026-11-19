"""Central tournament scoreboard server. Standard library only.

    python tournament/server.py --port 8000 --boards 4 --duration 600

Pages:
    /          big-screen display (8 teams, live scores, countdown, grand total when time is up)
    /control   organiser page: team names, start/stop round, next round, display override
    /board?n=1 manual score entry for a board without a working camera

API (JSON):
    GET  /api/state           full state
    GET  /api/round           round info + seconds_left (used by the board apps)
    POST /api/board/<n>       {"teams": [..], "scores": [..], "targets": [..], "current": 0}
    POST /api/round/start     {"duration": seconds} (optional)
    POST /api/round/stop
    POST /api/round/next      archive this round's scores into the grand totals, reset boards
    POST /api/config          {"boards": {"1": {"teams": [..]}}, "duration": s, "display": "auto|boards|totals"}
    POST /api/reset           wipe everything
"""

import argparse
import json
import os
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')
STATE_FILE = os.path.join(HERE, 'state.json')

lock = threading.Lock()
state = {}


def fresh_board(n):
    return {'teams': [f'Team {2*n-1}', f'Team {2*n}'], 'scores': [0, 0],
            'targets': ['T10', 'T10'], 'current': 0, 'source': None, 'updated': None}


def fresh_state(num_boards, duration):
    return {
        'round': {'number': 1, 'duration': duration, 'started_at': None, 'status': 'idle'},
        'boards': {str(n): fresh_board(n) for n in range(1, num_boards + 1)},
        'totals': {},
        'history': [],
        'display': 'auto',
    }


def save():
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def round_info():
    rnd = state['round']
    seconds_left = None
    if rnd['status'] == 'running':
        seconds_left = max(0.0, rnd['started_at'] + rnd['duration'] - time.time())
        if seconds_left <= 0:
            rnd['status'] = 'finished'
            seconds_left = 0
    return {**rnd, 'seconds_left': seconds_left}


def public_state():
    info = round_info()
    totals = dict(state['totals'])
    for board in state['boards'].values():
        for team, score in zip(board['teams'], board['scores']):
            totals[team] = totals.get(team, 0) + score
    return {'round': info, 'boards': state['boards'], 'totals': state['totals'],
            'grand_totals': totals, 'display': state['display'], 'server_time': time.time()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.command == 'GET' and self.path.startswith('/api/'):
            return
        super().log_message(fmt, *args)

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name):
        path = os.path.join(STATIC, name)
        if not os.path.isfile(path):
            return self._json({'error': 'not found'}, 404)
        with open(path, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        path = urlparse(self.path).path
        with lock:
            if path == '/api/state':
                return self._json(public_state())
            if path == '/api/round':
                return self._json(round_info())
        pages = {'/': 'display.html', '/display': 'display.html', '/control': 'control.html', '/board': 'board.html'}
        if path in pages:
            return self._file(pages[path])
        self._json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._body()
        except ValueError:
            return self._json({'error': 'bad json'}, 400)
        with lock:
            result = self._handle_post(path, data)
            save()
        if result is None:
            return self._json({'error': 'not found'}, 404)
        self._json(result)

    def _handle_post(self, path, data):
        rnd = state['round']
        if path.startswith('/api/board/'):
            n = path.rsplit('/', 1)[-1]
            if n not in state['boards']:
                return None
            if round_info()['status'] == 'finished':
                return {'ok': False, 'reason': 'round finished', 'round': round_info()}
            board = state['boards'][n]
            for key in ('teams', 'scores', 'targets', 'current', 'source'):
                if key in data:
                    board[key] = data[key]
            board['updated'] = time.time()
            return {'ok': True, 'round': round_info()}
        if path == '/api/round/start':
            rnd['duration'] = int(data.get('duration') or rnd['duration'])
            rnd['started_at'] = time.time()
            rnd['status'] = 'running'
            for board in state['boards'].values():
                board.update({'scores': [0, 0], 'targets': ['T10', 'T10'], 'current': 0})
            return round_info()
        if path == '/api/round/stop':
            if rnd['status'] == 'running':
                rnd['duration'] = int(time.time() - rnd['started_at'])
            rnd['status'] = 'finished'
            return round_info()
        if path == '/api/round/next':
            for n, board in state['boards'].items():
                for team, score in zip(board['teams'], board['scores']):
                    state['totals'][team] = state['totals'].get(team, 0) + score
                    state['history'].append({'round': rnd['number'], 'board': n, 'team': team, 'score': score})
                board.update({'scores': [0, 0], 'targets': ['T10', 'T10'], 'current': 0})
            rnd.update({'number': rnd['number'] + 1, 'started_at': None, 'status': 'idle'})
            return public_state()
        if path == '/api/config':
            for n, cfg in (data.get('boards') or {}).items():
                if n in state['boards'] and 'teams' in cfg:
                    state['boards'][n]['teams'] = [str(t)[:24] for t in cfg['teams']][:2]
            if data.get('duration'):
                rnd['duration'] = int(data['duration'])
            if data.get('display') in ('auto', 'boards', 'totals'):
                state['display'] = data['display']
            return public_state()
        if path == '/api/reset':
            keep = {n: b['teams'] for n, b in state['boards'].items()}
            state.update(fresh_state(len(state['boards']), rnd['duration']))
            for n, teams in keep.items():
                state['boards'][n]['teams'] = teams
            return public_state()
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--boards', type=int, default=4)
    parser.add_argument('--duration', type=int, default=600, help='round length in seconds')
    parser.add_argument('--fresh', action='store_true', help='ignore saved state.json')
    args = parser.parse_args()

    global state
    if os.path.isfile(STATE_FILE) and not args.fresh:
        with open(STATE_FILE) as f:
            state = json.load(f)
        print(f'Loaded saved state from {STATE_FILE} (use --fresh to start over)')
    else:
        state = fresh_state(args.boards, args.duration)
    save()

    server = ThreadingHTTPServer(('0.0.0.0', args.port), Handler)
    print(f'Display:  http://<this-machine-ip>:{args.port}/')
    print(f'Control:  http://<this-machine-ip>:{args.port}/control')
    print(f'Manual:   http://<this-machine-ip>:{args.port}/board?n=1')
    server.serve_forever()


if __name__ == '__main__':
    main()
