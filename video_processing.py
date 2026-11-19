from ultralytics import YOLO
from get_scores import GetScores

import cv2
import numpy as np
import sys
import threading
import time

class VideoProcessing:
    def __init__(self, model_dir="weights.pt", auto_commit_seconds=3.0, device=None):
        self.model = YOLO(model_dir)
        self.predict = GetScores(model_dir)
        self.device = device  # None = ultralytics default (CPU), 'mps' = Apple GPU, '0' = first CUDA GPU
        # USB cameras are opened by us so the resolution is under control; webcams otherwise
        # often deliver 640x480, which is too little for dart tips.
        self.camera_size = (1920, 1080)
        self.camera_fps = 30
        # a visit with fewer than 3 detected darts (bounce-out, missed dart) commits by itself
        # once no dart has been seen on the board for this long. None disables it.
        self.auto_commit_seconds = auto_commit_seconds
        self.last_dart_seen = None
    
    def _distance(self, coord1, coord2):
        return np.sqrt(np.sum((coord1 - coord2) ** 2))

    def _assess_visit(self, darts):
        darts = [dart for dart in darts if dart != '']
        if self.scorer.ruleset == 'triples':
            return self._assess_visit_triples(darts)
        score=0
        for dart in darts:
            score += self.scorer.get_score_for_dart(dart)
        
        remaining = self.scorer.scores[self.scorer.current_player] - score

        if remaining <= 1 or len(darts) == 3:
            if self.wait_for_dart_removal == False:
                self.scorer.read_score(score)

            self.wait_for_dart_removal = True
        else:
            self.wait_for_dart_removal = False

        if (remaining == 0 and darts[-1][0] != 'D') or remaining == 1 or remaining < 0:
            remaining = 'BUST'
        
        return score, remaining


    def _assess_visit_triples(self, darts):
        score = self.scorer.triples_visit_points(darts)
        running_total = self.scorer.scores[self.scorer.current_player] + score

        if len(darts) == 3 or self.scorer.locked:
            if self.wait_for_dart_removal == False and not self.scorer.locked:
                self.scorer.read_score(score)
            self.wait_for_dart_removal = True
        else:
            self.wait_for_dart_removal = False
        return score, running_total

    def _commit_score(self):
        self.scorer.commit_score([dart for dart in self.darts_in_visit if dart != ''])
        self.dart_coords_in_visit, self.darts_in_visit = [], ['']*3
        self.user_calibration = -np.ones((6, 2))
        self.wait_for_dart_removal = False
        self.pred_queue = -np.ones((5,3,2))
        self.pred_queue_count = 0
        self.last_dart_seen = None


    def _adjust_coords(self, calibration_coords, dart_coords, resolution, crop_start, crop_size):
        # needed in order to adjust the coords for the square crop
        calibration_coords *= resolution # get pixel coords
        calibration_coords -= crop_start # adjust pixel coords for square crop
        calibration_coords /= crop_size # convert back to normalised coords
        if dart_coords.shape != (0,): # do same for darts
            dart_coords *= resolution
            dart_coords -= crop_start
            dart_coords /= crop_size
            dart_coords = dart_coords[np.all(np.logical_and(dart_coords>=0, dart_coords<=1), axis=1)] # remove any dart points detected outside of square crop
        
        return calibration_coords, dart_coords

    def _process_predictions(self, transformed_dart_coords, repeat_threshold):
        if len(transformed_dart_coords) == 0:
            self.pred_queue[self.pred_queue_count % 5] = -np.ones((3, 2))
        else:
            self.last_dart_seen = time.time()
            self.pred_queue[self.pred_queue_count % 5] = np.vstack((transformed_dart_coords, -np.ones((3-len(transformed_dart_coords), 2)))) # add [-1, -1] to fill any spaces when < 3 darts
        self.pred_queue_count += 1

        if self.wait_for_dart_removal:
            count = 0
            for frame in self.pred_queue:
                if np.all(frame == -1):
                    count += 1
            if count >= repeat_threshold:
                self._commit_score()
        
        elif (self.auto_commit_seconds and len(self.dart_coords_in_visit) > 0 and self.last_dart_seen
              and np.all(self.pred_queue == -1) and time.time() - self.last_dart_seen > self.auto_commit_seconds):
            # darts were thrown and have since been pulled without reaching 3: commit what we saw
            self.scorer.read_score(self.scorer.triples_visit_points(self.darts_in_visit) if self.scorer.ruleset == 'triples'
                                   else sum(self.scorer.get_score_for_dart(d) for d in self.darts_in_visit if d))
            self._commit_score()

        elif self.darts_in_visit.count('') > 0:
            # check based on number of darts in visit and if the dart has been scored before
            unique_predictions = np.unique(self.pred_queue[self.pred_queue != -1].reshape(-1,2), axis=0)
            matches = {tuple(pred): [] for pred in unique_predictions} # for grouping together all similar predictions
            
            for frame in self.pred_queue:
                for pred in frame:
                    if np.any(pred == -1):
                        continue
                    for unique_pred in unique_predictions:
                        if self._distance(pred, unique_pred) < 0.01: # assume same prediction if distance < 0.01
                            matches[tuple(unique_pred)].append(pred)
                            break
            # sort dictionary based on length of values lists
            matches = {k: v for k, v in sorted(matches.items(), key=lambda item: len(item[1]), reverse=True) if len(v) >= repeat_threshold}
            best_predictions = []
            for _, match_ in matches.items():
                best_predictions.append(np.mean(match_, axis=0))
            
            if len(self.dart_coords_in_visit) == 0:
                self.dart_coords_in_visit = [pred for pred in best_predictions[:3]]
            
            else:
                for best_pred in best_predictions:
                    if all([self._distance(coords, best_pred) > 0.01 for coords in self.dart_coords_in_visit]):
                        if len(self.dart_coords_in_visit) == 3:
                            break
                        self.dart_coords_in_visit.append(best_pred)


    @staticmethod
    def resolve_source(source):
        """'0', '1', ... -> USB/built-in camera index; a full URL is used as is;
        anything else is treated as an IP Webcam host:port."""
        source = str(source).strip()
        if source.isdigit():
            return int(source)
        if source.startswith(('http://', 'https://', 'rtsp://')):
            return source
        return 'http://' + source + '/video'

    def _usb_results(self, index, predict_kwargs):
        """Open a USB/built-in camera at the configured size and yield one YOLO result per
        fresh frame. A reader thread always keeps the latest frame, so inference that is
        slower than the camera never builds up a delay."""
        backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            raise RuntimeError(f'camera {index} could not be opened')
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))   # compressed: several cameras fit on one USB bus
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_size[1])
        cap.set(cv2.CAP_PROP_FPS, self.camera_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        got = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if got != tuple(self.camera_size):
            print(f'Camera {index}: asked for {self.camera_size[0]}x{self.camera_size[1]}, got {got[0]}x{got[1]}')

        latest = {'seq': 0, 'frame': None, 'error': None}
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    latest['error'] = 'camera read failed'
                    break
                latest['frame'], latest['seq'] = frame, latest['seq'] + 1
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        try:
            seen = 0
            while True:
                if latest['error']:
                    raise RuntimeError(f'camera {index}: {latest["error"]}')
                if latest['seq'] == seen:
                    time.sleep(0.002)
                    continue
                seen, frame = latest['seq'], latest['frame']
                yield self.model.predict(frame, verbose=False, **predict_kwargs)[0]
        finally:
            stop.set()
            thread.join(timeout=2)
            cap.release()

    def start(self, GUI, source, scorer, resolution=None):
        self.scorer = scorer
        self.num_corrections = 0

        # resolution (width, height) is taken from the first frame, so any camera works
        crop_size, crop_start = None, None

        self.dart_coords_in_visit, self.darts_in_visit = [], ['']*3
        self.user_calibration = -np.ones((6, 2))
        self.wait_for_dart_removal = False
        self.last_dart_seen = None
        self.game_over = False

        self.pred_queue = -np.ones((5,3,2)) # implement FIFO queue to store the last 5 frames' predictions
        self.pred_queue_count = 0
        repeat_threshold = 3 # threshold number of frames to commit a dart

        prev_frame_time = 0
        new_frame_time = 0

        kwargs = {'device': self.device} if self.device else {}
        resolved = self.resolve_source(source)
        if isinstance(resolved, int):
            results = self._usb_results(resolved, kwargs)
        else:
            results = self.model(resolved, stream=True, verbose=False, **kwargs)

        for result in results:

            if self.game_over:
                break

            if crop_size is None:
                height, width = result.orig_shape[:2]
                resolution = np.array((width, height), dtype=float)
                crop_size = min(resolution)
                crop_start = resolution/2 - crop_size/2
                print(f'Camera frame {width}x{height}')
            
            calibration_coords, dart_coords = self.predict.process_yolo_output(result)
            if np.count_nonzero(calibration_coords == -1)/2 > 2:
                continue
            calibration_coords, dart_coords = self._adjust_coords(calibration_coords, dart_coords, resolution, crop_start, crop_size)
            calibration_coords = np.where(self.user_calibration == -1, calibration_coords, self.user_calibration)

            H_matrix = self.predict.find_homography(calibration_coords, crop_size)
            transformed_dart_coords = self.predict.transform_to_boardplane(H_matrix[0], dart_coords, crop_size)
            
            self._process_predictions(transformed_dart_coords, repeat_threshold)
            
            self.darts_in_visit, score = self.predict.score(np.array(self.dart_coords_in_visit)) # must always run this in case user moves coords
            while len(self.darts_in_visit) < 3:
                self.darts_in_visit.append('')
            
            score, remaining = self._assess_visit(self.darts_in_visit)

            new_frame_time = time.time()
            fps = round(1/(new_frame_time - prev_frame_time), 1)
            prev_frame_time = new_frame_time
            
            GUI._display_graphics(result, H_matrix, crop_start, crop_size, calibration_coords, dart_coords, score, remaining, fps)

        print(f'Number of user corrections: {self.num_corrections}')
        print(f'Number of darts thrown: {np.sum(self.scorer.num_dart_history)}')

if __name__ == "__main__":
    pass
    #game = GameLogic(ruleset='x01', player_names=['Ben'], x01=1001, num_legs=1)
    #AI_scorer = VideoDetection()
    #AI_scorer.start("192.168.0.68:8080", game, np.array((1200, 1600)))
    #AI_scorer.start("external", game)
    #AI_scorer.start("webcam", game)