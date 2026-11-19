"""Start one tournament board with no clicking: straight into a triples game.

    python board.py --board 1 --server http://192.168.0.10:8000 --camera 0
    python board.py --board 2 --server http://192.168.0.10:8000 --camera rtsp://192.168.0.22:554/stream1

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
    parser.add_argument('--model', default='weights.pt', help='weights.pt, or an exported model such as weights_ncnn_model or weights_openvino_model')
    parser.add_argument('--device', default=None, help="inference device: leave empty for CPU, 'mps' for an Apple GPU, '0' for an NVIDIA GPU")
    parser.add_argument('--width', type=int, default=1920, help='USB camera width (ignored for network cameras)')
    parser.add_argument('--height', type=int, default=1080, help='USB camera height')
    parser.add_argument('--fps', type=int, default=30, help='USB camera frame rate to request')
    args = parser.parse_args()

    app = GUI(args.model, args.device)
    app.video_processing.auto_commit_seconds = args.auto_commit or None
    app.video_processing.camera_size = (args.width, args.height)
    app.video_processing.camera_fps = args.fps
    app.start_tournament_board(args.board, args.server, args.camera, args.timer)


if __name__ == '__main__':
    main()
