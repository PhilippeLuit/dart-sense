# Hardware setup for a 4-board tournament

Two setups that work. Pick the one that fits the room.

**A. Four USB webcams on one gaming PC** (i9 / RTX 3080 class). Everything on
one machine: four boards, the server and the big screen on the TV. No screens
at the boards; players watch the big screen, the organiser corrects from a
phone. See *USB webcams on one PC* below.

**B. Four PoE IP cameras, one MacBook for the boards, a second Mac as server
and big screen.** No cable-length limit, cameras anywhere in the room.

## USB webcams on one PC

- Any recent desktop handles four streams. With an NVIDIA GPU use
  `--device 0`; the CPU alone is also enough.
- The app opens USB cameras itself at a fixed resolution in MJPEG mode
  (default 1920x1080 at 30 fps, change with `--width`, `--height`, `--fps`).
  Without that, webcams often deliver 640x480, which is too little.
- Spread the cameras over different USB controllers (front and back ports),
  or use two powered USB 3 hubs. Four 1080p MJPEG streams on one USB 2 hub
  do not fit.
- USB cables: 3 to 5 m passive, longer only with active extension cables.
- Camera numbers can change after a reboot. Check at start which window
  shows which board, or plug the cameras in always in the same order.
- Start everything on the PC:

  ```
  python tournament/server.py --port 8000 --boards 4 --duration 600
  python boards.py --server http://localhost:8000 --cameras 0 1 2 3 --device 0
  ```

  Big screen: a browser in full screen on `http://localhost:8000/` on the
  TV output. Organiser: `http://<pc-ip>:8000/control` on a phone.
- Windows: Python 3.11 or 3.12 from python.org (Tk included), PyTorch with
  CUDA per the ultralytics install notes, then `pip install ultralytics
  opencv-python pillow`.

## PoE IP cameras and a MacBook

```
 PoE camera bord 1 ─┐
 PoE camera bord 2 ─┤  PoE switch ── MacBook A (4 x board.py, via boards.py)
 PoE camera bord 3 ─┤       │
 PoE camera bord 4 ─┘       └────── MacBook B (server, control page, big screen → TV)
```

## Why this works

- Network cameras remove every USB limit: no hub, no 5 m cable limit, no
  bandwidth fight. Four 1080p streams are 20 to 40 Mbit/s together.
- Power and video go through one cable per camera, up to 100 m. The camera
  is mounted once and stays put, which keeps the calibration stable.
- A MacBook M-series runs YOLOv8n at 20 to 40 frames per second on the CPU
  for one stream, so four streams still give 5 to 10 per board. The app only
  needs a few frames per second: a dart counts after it repeats in 3 of the
  last 5 frames, and visits commit on a timer.
- The app accepts an RTSP address directly, no code change.

## Shopping list

| Item | Count | Note |
|------|-------|------|
| PoE IP camera with RTSP, 1080p or better | 4 (+1 spare) | Fixed focus or manual focus, 30 to 60 euro each |
| PoE switch, 5+ ports | 1 | Gigabit, enough PoE budget for 4 cameras |
| Network cable | 6 | 4 cameras, 2 Macs |
| Camera mounts | 4 | Rigid, out of the throwing line |
| LED lighting per board | 4 | Even light, no glare on the wires |
| MacBook (M-series, 16 GB) | 2 | A: boards, B: server + big screen |
| TV or beamer + HDMI/USB-C cable | 1 | Big screen |
| Phones with the manual page open | 4 | Fallback |

An Intel NUC or any laptop can stand in for either Mac. Keep one ready as
spare for the boards machine.

## Camera placement

- Above and slightly in front of the board, angled down, about 1 metre away.
  The full board with the four calibration points (outer corners of the 20,
  6, 3 and 11 doubles) fills most of the frame; dart tips stay visible.
- Rigid mount. If the camera moves mid-game the scores go wrong.
- Even, bright light, no glare. A cheap LED ring or strip around the board
  removes most detection failures.
- Fixed focus, 1080p, 15 to 25 frames per second is plenty. Higher frame
  rates only cost bandwidth.

## Network

- Give every camera, MacBook A and MacBook B a fixed IP address.
- Keep the tournament network separate from guests' Wi-Fi. Everything that
  matters is on the cable.
- Find each camera's RTSP address in its web interface, typically
  `rtsp://<ip>:554/stream1` or similar. Test it first with VLC or
  `ffplay`.

## MacBook A: the boards

Install once:

```
brew install python@3.12 python-tk@3.12
python3.12 -m venv .venv && source .venv/bin/activate
pip install ultralytics opencv-python pillow
```

Start all four boards with one command:

```
python boards.py --server http://<ip-macbook-b>:8000 \
    --cameras rtsp://<cam1>:554/stream1 rtsp://<cam2>:554/stream1 \
              rtsp://<cam3>:554/stream1 rtsp://<cam4>:554/stream1
```

Camera 1 is board 1, and so on. Each board gets its own window; a board that
crashes restarts by itself. Logs are in `logs/board<N>.log`. Options:

- `--device mps` uses the Apple GPU. Not needed, the CPU is fast enough; try
  it if a test shows the frame rate per board dropping below about 4.
- `--model weights_openvino_model` or another export, for Intel machines.

Settings on the Mac: no sleep with the lid open, screen never off, and allow
the Terminal to use the network when macOS asks. Put the MacBook between the
boards so players can glance at their window and correct a dart.

## MacBook B: server and big screen

```
python tournament/server.py --port 8000 --boards 4 --duration 600
```

Open `http://localhost:8000/` in a browser in full screen on the TV, and
`http://<ip-macbook-b>:8000/control` on the organiser's phone or laptop.
Standard library only, nothing to install.

## Before the event

1. Mount one camera, open its RTSP stream in the app, check detection with
   the real darts, board and lighting. Adjust position and light until the
   four calibration points and all darts are reliably found.
2. Repeat for all four, then run `boards.py` with all four streams and watch
   the frame rate per board in each window for at least half an hour.
3. Full rehearsal: server, big screen, control page, a round with the timer,
   a correction from the control page, and a board switched to the manual
   phone page.
4. Photograph the camera positions so they can be reproduced on the day.
