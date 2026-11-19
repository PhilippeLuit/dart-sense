"""Run several boards on one machine and keep them running.

    python boards.py --server http://192.168.0.10:8000 \
        --cameras rtsp://192.168.0.21:554/stream1 rtsp://192.168.0.22:554/stream1 \
                  rtsp://192.168.0.23:554/stream1 rtsp://192.168.0.24:554/stream1

Camera 1 becomes board 1, camera 2 board 2, and so on. Each board is its own
board.py process with its own window. A process that exits or crashes is
restarted after a few seconds. Ctrl-C stops them all. Output of each board
goes to logs/board<N>.log. Extra options (--device mps, --model ...) are passed
through to every board.
"""

import argparse
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--server', required=True)
    parser.add_argument('--cameras', nargs='+', required=True, help='one camera per board, in board order')
    parser.add_argument('--first-board', type=int, default=1, help='board number of the first camera')
    parser.add_argument('--restart-delay', type=float, default=3.0)
    args, passthrough = parser.parse_known_args()

    os.makedirs(os.path.join(HERE, 'logs'), exist_ok=True)
    procs = {}
    logs = {}

    def start(board, camera):
        log = open(os.path.join(HERE, 'logs', f'board{board}.log'), 'a')
        cmd = [sys.executable, os.path.join(HERE, 'board.py'), '--board', str(board), '--server', args.server, '--camera', camera] + passthrough
        log.write(f'\n=== {time.strftime("%H:%M:%S")} starting: {" ".join(cmd)}\n'); log.flush()
        procs[board] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
        logs[board] = log
        print(f'board {board}: started (pid {procs[board].pid}) camera {camera}')

    boards = {args.first_board + i: cam for i, cam in enumerate(args.cameras)}
    for board, camera in boards.items():
        start(board, camera)

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        while not stopping:
            for board, camera in boards.items():
                p = procs[board]
                if p.poll() is not None:
                    print(f'board {board}: exited with code {p.returncode}, restarting in {args.restart_delay:.0f} s')
                    logs[board].close()
                    time.sleep(args.restart_delay)
                    if not stopping:
                        start(board, camera)
            time.sleep(1)
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        for log in logs.values():
            log.close()
        print('all boards stopped')


if __name__ == '__main__':
    main()
