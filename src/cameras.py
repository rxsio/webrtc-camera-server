import threading
from typing import Optional

import gi
import pyudev
import yaml

from config import PipelinesConfig, SignallerConfig
from utils import create_logger

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)


# region Camera

class Camera:
    def __init__(self, logger, config_signaller, turn_settings, path, id, name,
                 width, height, framerate):
        self.logger = logger
        self.config_signaller = config_signaller
        self.turn_settings = turn_settings

        self.path = path
        self.id = id
        self.name = name

        self.width = width
        self.height = height
        self.framerate = framerate

        self.log(f"Camera created")

        self.pipeline = None
        self.create_pipeline()
        self.start_pipeline()

    def log(self, message):
        self.logger.info(f"[{self.path}]: {message}")

    def create_pipeline(self):
        raise NotImplementedError()

    def start_pipeline(self):
        self.log("Stream started")

        if self.pipeline is None:
            return

        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def stop_pipeline(self):
        self.log("Stream stopped")

        if self.pipeline is None:
            return

        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def restart_pipeline(self):
        self.log("Stream Restarted")

        self.stop_pipeline()
        self.start_pipeline()

    def on_message(self, bus, message):
        self.log(message)

        message_type = message.type

        if message_type == Gst.MessageType.EOS:
            self.log("Stream Ended")
            self.restart_pipeline()
        elif message_type == Gst.MessageType.ERROR:
            self.player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            self.log(f"Stream error {err}: {debug}")
            self.restart_pipeline()

    def __del__(self):
        self.stop_pipeline()
        self.log(f"Camera Destroyed")


class H264Camera(Camera):
    def create_pipeline(self):
        self.pipeline = Gst.Pipeline.new("pipeline")
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        source = Gst.ElementFactory.make("v4l2src", "camera-source")
        capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
        h264parse = Gst.ElementFactory.make("h264parse", "parse")
        avdec_h264 = Gst.ElementFactory.make("avdec_h264", "decode")
        sink = Gst.ElementFactory.make("webrtcsink", "webrtc")

        self.pipeline.add(source)
        self.pipeline.add(capsfilter)
        self.pipeline.add(h264parse)
        self.pipeline.add(avdec_h264)
        self.pipeline.add(sink)

        source.set_property("device", self.path)
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string(
                f"video/x-h264, width=${self.width}, height=${self.height}, framerate=${self.framerate}/1"
            ),
        )

        sink_config = Gst.Structure.new_empty("meta")
        sink_config.set_value("name", self.name)
        sink.set_property("meta", sink_config)

        if self.turn_settings is not None:
            sink.set_property("turn-servers", Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        uri = f"wss://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)
        signaller.set_property("cafile", self.config_signaller.certificate)

        source.link(capsfilter)
        capsfilter.link(h264parse)
        h264parse.link(avdec_h264)
        avdec_h264.link(sink)


class MJPEGCamera(Camera):
    def create_pipeline(self):
        self.pipeline = Gst.Pipeline.new("pipeline")
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        source = Gst.ElementFactory.make("v4l2src", "camera-source")
        capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
        jpegdec = Gst.ElementFactory.make("jpegdec", "decode")
        sink = Gst.ElementFactory.make("webrtcsink", "webrtc")

        self.pipeline.add(source)
        self.pipeline.add(capsfilter)
        self.pipeline.add(jpegdec)
        self.pipeline.add(sink)

        source.set_property("device", self.path)
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string(
                f"image/jpeg, width=${self.width}, height=${self.height}, framerate=${self.framerate}/1"
            ),
        )

        sink_config = Gst.Structure.new_empty("meta")
        sink_config.set_value("name", self.name)
        sink.set_property("meta", sink_config)

        if self.turn_settings is not None:
            sink.set_property("turn-servers", Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        uri = f"wss://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)
        signaller.set_property("cafile", self.config_signaller.certificate)

        source.link(capsfilter)
        capsfilter.link(jpegdec)
        jpegdec.link(sink)


# endregion


class CamerasManager:

    def __init__(self, config: PipelinesConfig,
                 config_signaller: SignallerConfig,
                 turn_settings: Optional[list]):
        self.config = config
        self.config_signaller = config_signaller
        self.turn_settings = turn_settings

        self.cameras = {}
        self.lock = threading.Lock()
        self.udev_context = pyudev.Context()

        self.logger = create_logger("Cameras")

    def detect_cameras(self):
        self.logger.debug("Detecting cameras")

        counter = 0
        for device in self.udev_context.list_devices(
                subsystem="video4linux", ID_V4L_CAPABILITIES=":capture:"
        ):
            self.add_camera(device)
            counter += 1

        self.logger.debug(f"{counter} cameras detected")

    def add_camera(self, device):
        self.logger.debug(f"Adding camera: {device}")

        id_path = device.get("ID_PATH")
        id_sanitized = device.get("ID_PATH_TAG")
        path = device.device_node
        serial = device.get("ID_SERIAL_SHORT")
        vendor = device.get("ID_VENDOR")
        model = device.get("ID_MODEL")

        name = id_sanitized
        protocol = "mjpeg"
        width = 1280
        height = 720
        framerate = 10

        if id_path in self.config.cameras:
            camera_config = self.config.cameras[id_path]
            name = camera_config["name"]
            protocol = camera_config["protocol"]
            width = camera_config["width"]
            height = camera_config["height"]
            framerate = camera_config["framerate"]
            self.logger.info(
                f"adding camera {name} with id={id_path} path={path}")
        else:
            self.logger.info(
                f"adding unknown camera with id={id_path} path={path}")
            self.logger.info(f"used config:")
            self.logger.info(
                yaml.dump(
                    {
                        "cameras": {
                            id_path: {
                                "name": name,
                                "protocol": protocol,
                                "width": width,
                                "height": height,
                                "framerate": framerate,
                            }
                        }
                    },
                    sort_keys=False,
                )
            )

        self.lock.acquire(blocking=True)

        if protocol == "h264":
            self.cameras[id_path] = H264Camera(
                logger=self.logger, config_signaller=self.config_signaller,
                turn_settings=self.turn_settings, path=path, id=id_path,
                name=name,
                width=width, height=height,
                framerate=framerate
            )
        elif protocol == "mjpeg":
            self.cameras[id_path] = MJPEGCamera(
                logger=self.logger, config_signaller=self.config_signaller,
                turn_settings=self.turn_settings, path=path, id=id_path,
                name=name,
                width=width, height=height,
                framerate=framerate
            )

        self.lock.release()

    def remove_camera(self, device):
        id_path = device.get("ID_PATH")

        self.lock.acquire(blocking=True)

        self.logger.info(
            f"removing camera {self.cameras[id_path].name}"
            f" with id={id_path} path={self.cameras[id_path].path}"
        )
        self.cameras[id_path].stop_pipeline()
        del self.cameras[id_path]

        self.lock.release()

    def start_camera_monitoring(self):
        self.logger.debug("Start Camera monitoring")

        monitor = pyudev.Monitor.from_netlink(self.udev_context)
        monitor.filter_by("video4linux")

        def log_event(action, device):
            if device.get("ID_V4L_CAPABILITIES") == ":capture:":
                self.logger.info(action, device)

                if action == "add":
                    self.add_camera(device)
                elif action == "remove":
                    self.remove_camera(device)

        observer = pyudev.MonitorObserver(monitor, log_event)
        self.logger.debug("Start observer")
        observer.start()
