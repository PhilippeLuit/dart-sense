# Hardware setup for a 4-board tournament

Recommended: **one laptop per board with a USB webcam**, one extra laptop for
the scoreboard server and the big screen.

## Why one laptop per board

- Each board is isolated. If one laptop or camera fails, the other three games
  keep running and that board switches to the manual scoring page.
- Players see their live score, the detected darts and the timer at the board,
  and can correct a misread dart there. That needs a screen and a mouse.
- CPU inference is enough for one stream. YOLOv8n runs at roughly 10 to 30
  frames per second on a recent laptop CPU, and a dart commits after it repeats
  in 3 of the last 5 frames, so a few frames per second is enough. No GPU needed.
- The laptop battery doubles as a UPS when a power strip gets kicked.

One machine driving all four cameras is the worse option: USB cable length is
limited to a few metres, four cameras compete for USB bandwidth, and one crash
stops the whole tournament.

## Why USB webcams instead of phones

- No video over Wi-Fi. Only small score updates cross the network.
- No phone battery, overheating or screen timeout problems during a long evening.
- One cable per board, and nobody's personal phone is tied up.

A 1080p webcam with a decent sensor, in the class of a Logitech C920 or C922,
is plenty. Set focus to manual if the camera allows it, keep auto exposure on.
In the app, enter the camera index (`0` for the first camera, `1` for the next)
instead of an IP address. The app reads the frame size from the camera.

## Camera placement matters more than the camera

- Mount it rigidly: a clamp arm or microphone boom on the wall or a stand. Not a
  tripod on the floor where it gets bumped. If the camera moves mid-game the
  calibration shifts and scores go wrong.
- Above and slightly in front of the board, angled down, about 1 metre away.
  The full board with all four calibration points (the outer corners of the 20,
  6, 3 and 11 double segments) should fill most of the frame, and dart tips must
  stay visible.
- Even, bright light with no glare on the wires. A cheap LED ring or strip
  around the board removes most detection failures.
- Keep the camera out of the throwing line and away from where players stand to
  pull their darts.

## The rest of the kit

- One laptop for the scoreboard server and the organiser page. It can drive the
  big screen over HDMI. The server is light enough to share a board laptop.
- A TV or beamer for the big screen, any browser in full screen on `/`.
- A dedicated small router. Ethernet to the board laptops if cables are
  practical, otherwise Wi-Fi is fine since no video crosses it.
- Four phones or tablets with the manual scoring page (`/board?n=1` to `4`)
  open, as the fallback.
- Power strips, USB extension cables, one spare webcam.

## Shopping list per board

| Item | Note |
|------|------|
| Laptop, recent CPU, 8 GB RAM | Any machine from the last 4 years |
| 1080p USB webcam | C920 class |
| Clamp arm or boom mount | Rigid, out of the throwing line |
| USB extension, 3 m | Active cable if longer |
| LED lighting | Even light, no glare |

## Before the event

1. Install the app on every board laptop and run a game with the real webcam.
2. Set up the exact camera position and lighting at the venue, test detection,
   and photograph the setup so it can be reproduced on the day.
3. Do a full rehearsal with all four boards, the server, the big screen and the
   manual pages on the venue network.
