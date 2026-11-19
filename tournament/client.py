"""Background reporter that keeps one board's Dart Sense instance in sync with the
central tournament server. Never blocks the video loop: all HTTP runs in a thread."""

import json
import threading
import time
import urllib.request
import urllib.error


class ScoreReporter(threading.Thread):
    def __init__(self, server_url, board, local_duration_s=600, interval=1.0):
        super().__init__(daemon=True)
        self.server_url = server_url.rstrip('/')
        self.board = int(board)
        self.interval = interval
        self.state = None            # dict set by the GUI thread; posted when changed
        self._last_sent = None
        self.connected = False
        self.round = {}              # last round info from the server
        self.round_ends_at = None    # local clock time at which the round ends
        self.round_started_at = None
        self.local_ends_at = time.time() + local_duration_s if local_duration_s else None
        self.on_round_start = None   # callback(round_info) invoked when a new round starts

    # --- called from the GUI thread -------------------------------------------------
    def seconds_left(self):
        ends_at = self.round_ends_at if self.connected and self.round.get('status') == 'running' else None
        if ends_at is None and self.connected and self.round.get('status') in ('idle', 'finished'):
            return None if self.round.get('status') == 'idle' else 0
        if ends_at is None:
            ends_at = self.local_ends_at
        if ends_at is None:
            return None
        return max(0.0, ends_at - time.time())

    def time_is_up(self):
        left = self.seconds_left()
        return left is not None and left <= 0

    # --- background loop --------------------------------------------------------------
    def run(self):
        while True:
            try:
                self._poll_round()
                if self.state is not None and self.state != self._last_sent:
                    self._post_state()
                self.connected = True
            except (urllib.error.URLError, OSError, ValueError):
                self.connected = False
            time.sleep(self.interval)

    def _request(self, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.server_url + path, data=body,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST' if body else 'GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode())

    def _poll_round(self):
        info = self._request('/api/round')
        previous_start = self.round.get('started_at')
        self.round = info
        if info.get('status') == 'running' and info.get('seconds_left') is not None:
            self.round_ends_at = time.time() + float(info['seconds_left'])
        else:
            self.round_ends_at = None
        if info.get('started_at') and info.get('started_at') != previous_start and self.on_round_start:
            self._last_sent = None
            self.on_round_start(info)

    def _post_state(self):
        payload = dict(self.state)
        self._request(f'/api/board/{self.board}', payload)
        self._last_sent = payload
