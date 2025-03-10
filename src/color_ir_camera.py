import cv2
import numpy as np
import socket
import time
import threading
from typing import Any, Callable, Dict, List, Tuple


Frame = np.ndarray
Transformation = Callable[[Frame], Frame]


class Runner:
    def __init__(self, host: str, receive_port: int, send_port: int, width: int, height: int, pipeline: 'Pipeline'):
        self._host = host
        self._receive_port = receive_port
        self._send_port = send_port
        self._frame_size = width * height * 2
        self._last_frame = None
        self._socket = None
        self._width = width
        self._height = height
        self._pipeline = pipeline
        self._lock = threading.Lock()

        self._initialize_socket()

    @property
    def last_frame(self):
        with self._lock:
            return self._last_frame

    @last_frame.setter
    def last_frame(self, frame):
        with self._lock:
            self._last_frame = frame

    @property
    def pipeline(self):
        with self._lock:
            return self._pipeline

    @pipeline.setter
    def pipeline(self, pipeline):
        with self._lock:
            self._pipeline = pipeline

    def _create_socket(self, host: str, port: int):
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind((host, port))
                return sock
            except socket.error as e:
                print(f"Error creating socket: {e}")
                time.sleep(1)

    def _initialize_socket(self):
        self._socket = self._create_socket(self._host, self._receive_port)

    def _restart_socket(self):
        if self._socket:
            self._socket.close()
        self._socket = self._create_socket(self._host, self._receive_port)

    def run(self):
        while True:
            try:
                data, addr = self._socket.recvfrom(self._frame_size)
                if len(data) == self._frame_size:
                    frame = np.frombuffer(data, dtype='<u2').reshape((self._height, self._width))
                    frame = frame[:-2, :] # Fix image
                    self.last_frame = frame
                    processed_frame = self.pipeline.apply(frame)
                    self._socket.sendto(processed_frame.tobytes(), (self._host, self._send_port))
            except Exception as e:
                print(f"Socket error: {e}, attempting to restart socket.")
                self._restart_socket()
                time.sleep(1)

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()


class Pipeline:

    def __init__(self, width: int, height: int, transformations: List[Transformation], features: Dict[str, Any]):
        self._width = width
        self._height = height
        self._transformations = transformations
        self._features = features

    def get_temperature_at(self, frame: Frame, x: int, y: int) -> float:
        if y < 0 or y >= self._height:
            raise ValueError(f"Y should be in range [0; {self._height - 1}]")

        if x < 0 or x >= self._width:
            raise ValueError(f"X should be in range [0; {self._width - 1}]")

        return self._convert_to_temperature(
            float(frame[y, x])
        )

    def get_min_temperature(self, frame: Frame) -> Tuple[float, Tuple[int, int]]:
        position = np.unravel_index(np.argmin(frame), frame.shape)
        position = int(position[1]), int(position[0])

        return self.get_temperature_at(frame, *position), position

    def get_max_temperature(self, frame: Frame) -> Tuple[float, Tuple[int, int]]:
        position = np.unravel_index(np.argmax(frame), frame.shape)
        position = int(position[1]), int(position[0])

        return self.get_temperature_at(frame, *position), position

    def apply(self, frame: Frame) -> Frame:
        if self._features.get("mark_min_temp", None):
            _, min_pos = self.get_min_temperature(frame)

        if self._features.get("mark_max_temp", None):
            _, max_pos = self.get_max_temperature(frame)

        for transform in self._transformations:
            frame = transform(frame)

        if self._features.get("mark_min_temp", None):
            frame = self._mark_position(
                frame,
                min_pos,
                self._features.get("mark_min_temp::color", (255, 255, 255))
            )

        if self._features.get("mark_max_temp", None):
            frame = self._mark_position(
                frame,
                max_pos,
                self._features.get("mark_max_temp::color", (255, 255, 255))
            )

        return frame

    def _convert_to_temperature(self, value: int) -> float:
        return (value - 27315) / 100

    def _mark_position(self, frame: Frame, position: Tuple[int, int], color: Tuple[int, int, int]) -> Frame:
        return cv2.circle(frame, position, 1, color, -1)



class PipelineBuilder:

    def __init__(self, width: int, height: int):
        self._width = width
        self._height = height
        self._transformations = []
        self._features = {}

    def add_normalization(self, min: int = 0, max: int = 0, normalization_type: int = cv2.NORM_MINMAX) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.normalize(frame, None, min, max, normalization_type)
        )
        self._transformations.append(
            lambda frame: np.uint8(frame)
        )

        return self

    def add_clahe(self, clip_limit: float = 2.0, tile_grid_size: Tuple[int, int] = (16, 16)) -> 'PipelineBuilder':
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        self._transformations.append(
            lambda frame: clahe.apply(frame)
        )

        return self

    def add_histogram_equalization(self) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.equalizeHist(frame)
        )

        return self

    def add_gaussian_blur(self, kernel_size: Tuple[int, int] = (3, 3), sigma: Tuple[float, float] = (0.0, 0.0)) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.GaussianBlur(frame, kernel_size, *sigma)
        )

        return self

    def add_median_blur(self, diameter: int = 3) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.medianBlur(frame, diameter)
        )

        return self

    def add_bilateral_blur(self, diameter: int = 3, sigma_color: float = 30, sigma_space: float = 30) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.bilateralFilter(frame, diameter, sigma_color, sigma_space)
        )

        return self

    def add_color_map(self, color_map: int) -> 'PipelineBuilder':
        self._transformations.append(
            lambda frame: cv2.applyColorMap(frame, color_map)
        )

        return self

    def add_mark_min_temperature(self, color: Tuple[int, int, int] = (255, 255, 255)) -> 'PipelineBuilder':
        self._features["mark_min_temp"] = True
        self._features["mark_min_temp::color"] = color
        return self

    def add_mark_max_temperature(self, color: Tuple[int, int, int] = (255, 255, 255)) -> 'PipelineBuilder':
        self._features["mark_max_temp"] = True
        self._features["mark_max_temp::color"] = color
        return self

    def build(self) -> Transformation:
        return Pipeline(
            self._width,
            self._height,
            self._transformations,
            self._features
        )


if __name__ == "__main__":
    pipeline = PipelineBuilder(160, 120) \
        .add_normalization(0, 255, cv2.NORM_MINMAX) \
        .add_clahe(2.0, (16, 16)) \
        .add_bilateral_blur(3, 30, 30) \
        .add_color_map(cv2.COLORMAP_INFERNO) \
        .add_mark_min_temperature() \
        .add_mark_max_temperature((0, 0, 0)) \
        .build()

    runner = Runner("0.0.0.0", 5123, 5124, 160, 122, pipeline)
    runner.start()

    # In other thread
    while True:
        if runner.last_frame is not None:
            print(pipeline.get_max_temperature(runner.last_frame))
        time.sleep(1)