"""Central tournament scoreboard server. Standard library only.

    python tournament/server.py --port 8000 --boards 4 --duration 600

Pages:
    /          big-screen display (8 teams, live scores, countdown, grand total when time is up)
    /control   organiser page: team names, start/stop round, next round, display override
    /board?n=1 manual score entry for a board without a working camera

API (JSON):
    GET  /api/state           full state
    GET  /api/round           round info + seconds_left
    GET  /api/board/<n>       round info + that board's teams and scores (used by the board apps)
    POST /api/board/<n>       {"teams": [..], "scores": [..], "targets": [..], "current": 0}
    POST /api/board/<n>/hit   {"team": 0, "number": 14, "delta": 1}   organiser: one hit on 14 (+1) or one taken back (-1)
    POST /api/board/<n>/set   {"team": 0, "score": 90, "progress": [3,3,0,...]}   organiser: set values directly
    POST /api/round/start     {"duration": seconds} (optional)
    POST /api/round/stop
    POST /api/round/next      archive this round's scores into the grand totals, reset boards
    POST /api/config          {"boards": {"1": {"teams": [..]}}, "duration": s, "display": "auto|boards|totals|schedule"}
    POST /api/teams           {"teams": ["name", ...]}   the list of participating teams
    POST /api/schedule        {"schedule": [[["A","B"],["C","D"],...], ...]}  one list of matches per round, one match per board
    POST /api/schedule/generate {"rounds": 7}   round robin for the team list, trimmed to this many rounds
    POST /api/reset           scores, totals and round back to the start; teams and schedule are kept
"""

import argparse
import json
import mimetypes
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tournament import rules  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')
STATE_FILE = os.path.join(HERE, 'state.json')

lock = threading.Lock()
state = {}


def fresh_board(n):
    return {'teams': [f'Team {2*n-1}', f'Team {2*n}'], 'scores': [0, 0],
            'targets': [rules.fresh_progress(), rules.fresh_progress()],   # hits per number (0..3), per team
            'current': 0, 'source': None, 'updated': None}


def fresh_state(num_boards, duration):
    return {
        'round': {'number': 1, 'duration': duration, 'started_at': None, 'status': 'idle'},
        'boards': {str(n): fresh_board(n) for n in range(1, num_boards + 1)},
        'totals': {},
        'history': [],
        'display': 'auto',
        'teams': [],
        'schedule': [],
    }


def round_robin(teams):
    """Circle method: every team meets every other team once. Odd counts get a bye."""
    teams = list(teams)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a and b:
                pairs.append([a, b] if r % 2 == 0 else [b, a])
        rounds.append(pairs)
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return rounds


def apply_schedule(round_number):
    """Put the teams of this round on the boards. Boards without a match keep their names."""
    schedule = state.get('schedule') or []
    if round_number - 1 >= len(schedule):
        return
    for n, board in state['boards'].items():
        idx = int(n) - 1
        if idx < len(schedule[round_number - 1]):
            board['teams'] = list(schedule[round_number - 1][idx])


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
            'grand_totals': totals, 'display': state['display'], 'server_time': time.time(),
            'teams': state.get('teams', []), 'schedule': state.get('schedule', [])}


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
        path = os.path.normpath(os.path.join(STATIC, name))
        if not path.startswith(STATIC + os.sep) or not os.path.isfile(path):
            return self._json({'error': 'not found'}, 404)
        with open(path, 'rb') as f:
            body = f.read()
        ctype = 'text/html; charset=utf-8' if name.endswith('.html') else (mimetypes.guess_type(name)[0] or 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
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
            if path.startswith('/api/board/'):
                n = path.rsplit('/', 1)[-1]
                if n in state['boards']:
                    return self._json({'round': round_info(), 'board': state['boards'][n]})
        pages = {'/': 'display.html', '/display': 'display.html', '/control': 'control.html', '/board': 'board.html'}
        if path in pages:
            return self._file(pages[path])
        if path.startswith('/static/'):
            return self._file(path[len('/static/'):])
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
            parts = path.split('/')[3:]          # ['<n>'] or ['<n>', 'hit'|'set']
            n, action = parts[0], (parts[1] if len(parts) > 1 else None)
            if n not in state['boards']:
                return None
            board = state['boards'][n]
            if action in ('hit', 'set'):         # organiser corrections: allowed at any time
                team = int(data.get('team', 0))
                if team not in (0, 1):
                    return None
                if action == 'hit':
                    board['targets'][team], board['scores'][team] = rules.apply_correction(
                        board['targets'][team], board['scores'][team], int(data.get('number', 0)), int(data.get('delta', 1)))
                else:
                    if 'score' in data:
                        board['scores'][team] = max(0, int(data['score']))
                    if 'progress' in data:
                        board['targets'][team] = rules.normalise_progress(data['progress'])
                board['corrected_at'] = board['updated'] = time.time()
                return {'ok': True, 'board': board}
            if round_info()['status'] == 'finished':
                return {'ok': False, 'reason': 'round finished', 'round': round_info()}
            for key in ('teams', 'scores', 'targets', 'current', 'source'):
                if key in data:
                    board[key] = data[key]
            if 'targets' in data:
                board['targets'] = [rules.normalise_progress(p) for p in list(data['targets'])[:2]]
            board['updated'] = time.time()
            return {'ok': True, 'round': round_info()}
        if path == '/api/round/start':
            rnd['duration'] = int(data.get('duration') or rnd['duration'])
            rnd['started_at'] = time.time()
            rnd['status'] = 'running'
            apply_schedule(rnd['number'])
            for board in state['boards'].values():
                board.update({'scores': [0, 0], 'targets': [rules.fresh_progress(), rules.fresh_progress()], 'current': 0})
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
                board.update({'scores': [0, 0], 'targets': [rules.fresh_progress(), rules.fresh_progress()], 'current': 0})
            rnd.update({'number': rnd['number'] + 1, 'started_at': None, 'status': 'idle'})
            apply_schedule(rnd['number'])
            return public_state()
        if path == '/api/teams':
            names = []
            for t in data.get('teams') or []:
                t = str(t).strip()[:24]
                if t and t not in names:
                    names.append(t)
            state['teams'] = names
            return public_state()
        if path == '/api/schedule/generate':
            if len(state.get('teams', [])) < 2:
                return {'ok': False, 'reason': 'enter at least two teams first'}
            rounds = round_robin(state['teams'])
            if max(len(r) for r in rounds) > len(state['boards']):
                return {'ok': False, 'reason': f'{len(state["teams"])} teams need more than {len(state["boards"])} boards per round'}
            wanted = int(data.get('rounds') or len(rounds))
            state['schedule'] = rounds[:max(1, wanted)]
            if rnd['status'] == 'idle':
                apply_schedule(rnd['number'])
            return public_state()
        if path == '/api/schedule':
            schedule = []
            for matches in data.get('schedule') or []:
                schedule.append([[str(a)[:24], str(b)[:24]] for a, b in matches if str(a).strip() and str(b).strip()][:len(state['boards'])])
            state['schedule'] = schedule
            if rnd['status'] == 'idle':
                apply_schedule(rnd['number'])
            return public_state()
        if path == '/api/config':
            for n, cfg in (data.get('boards') or {}).items():
                if n in state['boards'] and 'teams' in cfg:
                    state['boards'][n]['teams'] = [str(t)[:24] for t in cfg['teams']][:2]
            if data.get('duration'):
                rnd['duration'] = int(data['duration'])
            if data.get('display') in ('auto', 'boards', 'totals', 'schedule'):
                state['display'] = data['display']
            return public_state()
        if path == '/api/reset':
            keep = {n: b['teams'] for n, b in state['boards'].items()}
            teams, schedule = state.get('teams', []), state.get('schedule', [])
            state.update(fresh_state(len(state['boards']), rnd['duration']))
            state['teams'], state['schedule'] = teams, schedule
            for n, names in keep.items():
                state['boards'][n]['teams'] = names
            apply_schedule(1)
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
