"""Start one tournament board with no clicking: straight into a triples game.

    python board.py --board 1 --server http://192.168.0.10:8000 --camera 0

Team names come from the organiser's control page on the server. The board
resets when the organiser starts a round, locks when time is up, commits a
visit by itself once the darts are pulled, and reconnects if the camera drops.
"""

import argparse

from GUI import GUI


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--board', type=int, required=True, help='board number, 1-4')
    parser.add_argument('--server', required=True, help='scoreboard server, e.g. http://192.168.0.10:8000')
    parser.add_argument('--camera', default='0', help='USB camera index (0, 1, ...) or IP Webcam host:port')
    parser.add_argument('--timer', type=float, default=10, help='fallback round length in minutes if the server is unreachable')
    parser.add_argument('--auto-commit', type=float, default=3.0,
                        help='seconds the board must be empty before a visit with fewer than 3 darts commits; 0 disables')
    args = parser.parse_args()

    app = GUI()
    app.video_processing.auto_commit_seconds = args.auto_commit or None
    app.start_tournament_board(args.board, args.server, args.camera, args.timer)


if __name__ == '__main__':
    main()
