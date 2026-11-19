# Tournament mode: 4 boards, 8 teams, one big screen

Game: **triples**. Two teams per board. Each team climbs its own ladder: hit
triple 10, then triple 11, and so on up to triple 20, then the bull. Only a dart
on the team's current target counts. Points per hit are the normal dart value
(T10 = 30, T20 = 60, bull = 50). Teams alternate 3-dart visits. All four boards
share one round timer. When time is up, every board locks and the big screen
switches to the grand total. Grand totals accumulate over rounds, keyed by team
name, so teams can rotate boards between rounds.

Hardware recommendations are in [HARDWARE.md](HARDWARE.md).

To change the ladder or the points, edit `tournament/rules.py` and the matching
`LADDER` in `tournament/static/board.html`.

## What it looks like

Big screen during a round, and the grand total when time is up:

![big screen during play](../images/tournament/display_boards.png)
![grand total](../images/tournament/display_totals.png)

Organiser control page and the manual scoring page for one board (phone):

<img src="../images/tournament/control.png" alt="control page" width="60%"> <img src="../images/tournament/manual_board.png" alt="manual scoring" width="30%">

## Parts

| Part | Where | Runs on |
|------|-------|---------|
| Central server | `python tournament/server.py --port 8000 --boards 4 --duration 600` | one laptop on the venue Wi-Fi |
| Big screen | `http://<server-ip>:8000/` | TV or beamer, any browser, full screen |
| Organiser control | `http://<server-ip>:8000/control` | organiser's phone or laptop |
| Manual scoring | `http://<server-ip>:8000/board?n=1` | fallback if a camera fails |
| Camera scoring | `python GUI.py`, game type `triples` | one Dart Sense instance per board |

The server only needs Python 3, no extra packages. State is saved to
`tournament/state.json` after every change, so a restarted server keeps scores
and totals. Start with `--fresh` to wipe it.

## Running a round

1. Start the server. Note the laptop's IP address.
2. Open `/control`, fill in the eight team names, set the round duration, save.
3. On each board laptop start `GUI.py`: game type `triples`, players 2, untick
   `Call scores`, fill in board number, the server URL, the phone's IP Webcam
   address, or `0` for a USB webcam. Enter the two team names and press Start. The window shows
   `Waiting for round start`.
4. Open `/` on the big screen.
5. Press `Start round` in `/control`. All boards reset to 0 and the countdown
   starts everywhere.
6. When the timer hits zero every board shows `TIME`, stops accepting scores,
   and the big screen shows the grand total.
7. Press `Next round` to add the round to the totals and reset the boards.
   Rename teams per board if they rotate, then `Start round` again.

`Stop now` ends a round early. The display override in `/control` forces the
big screen to boards or totals regardless of the timer.

## Board app behaviour

- The board app reports after every change and polls the server every second.
  If the server is unreachable it keeps scoring locally using the fallback
  timer from the setup screen, and shows `(server offline)`.
- The server rejects score updates once the round is finished, so a late
  report cannot change the result.
- A team that completes the ladder shows target `Done` and scores no more.
- The existing manual controls still work: `Add dart`, click and drag a dart
  marker to correct it, Enter to commit a visit with a bounce-out.
