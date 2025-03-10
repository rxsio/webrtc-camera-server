import threading
from typing import Optional

import gi
import pyudev
import yaml

from config import PipelinesConfig, SignallerConfig, CameraMode
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

    def debug(self, message):
        self.logger.debug(f"[{self.path}]: {message}")

    def error(self, message):
        self.logger.error(f"[{self.path}]: {message}")

    def create_pipeline(self):
        raise NotImplementedError()

    def start_pipeline(self):
        self.log("Stream started")

        if self.pipeline is None:
            self.error("Stream pipeline is Null")
            return

        self.pipeline.set_state(Gst.State.PLAYING)
        self.debug("Set pipeline state to PLAYING")
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def stop_pipeline(self):
        self.log("Stream stopped")

        if self.pipeline is None:
            self.info("Stream pipeline is Null")
            return

        self.pipeline.set_state(Gst.State.NULL)
        self.debug("Set pipeline state to NULL")
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
            self.debug(f"Adding TURN-SERVERS to camera {self.turn_settings}")
            sink.set_property("turn-servers",
                              Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        protocol = "wss" if self.config_signaller.secure == True else "ws"
        uri = f"{protocol}://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)

        if self.config_signaller.certificateCA is not None:
            signaller.set_property("cafile",
                                   self.config_signaller.certificateCA)

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
            self.debug(f"Adding TURN-SERVERS to camera {self.turn_settings}")
            sink.set_property("turn-servers",
                              Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        protocol = "wss" if self.config_signaller.secure == True else "ws"
        uri = f"{protocol}://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)

        if self.config_signaller.certificateCA is not None:
            signaller.set_property("cafile",
                                   self.config_signaller.certificateCA)

        source.link(capsfilter)
        capsfilter.link(jpegdec)
        jpegdec.link(sink)


class RawCamera(Camera):
    def create_pipeline(self):
        self.pipeline = Gst.Pipeline.new("pipeline")
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        source = Gst.ElementFactory.make("v4l2src", "camera-source")
        capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        queue = Gst.ElementFactory.make("queue", "queue")
        sink = Gst.ElementFactory.make("webrtcsink", "webrtc")

        self.pipeline.add(source)
        self.pipeline.add(capsfilter)
        self.pipeline.add(convert)
        self.pipeline.add(queue)
        self.pipeline.add(sink)

        source.set_property("device", self.path)
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string(
                f"video/x-raw, format=GRAY16_LE, width=${self.width}, height=${self.height}, framerate=${self.framerate}/1"
            ),
        )

        sink_config = Gst.Structure.new_empty("meta")
        sink_config.set_value("name", self.name)
        sink.set_property("meta", sink_config)

        if self.turn_settings is not None:
            self.debug(f"Adding TURN-SERVERS to camera {self.turn_settings}")
            sink.set_property("turn-servers",
                              Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        protocol = "wss" if self.config_signaller.secure == True else "ws"
        uri = f"{protocol}://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)

        if self.config_signaller.certificateCA is not None:
            signaller.set_property("cafile",
                                   self.config_signaller.certificateCA)

        source.link(capsfilter)
        capsfilter.link(convert)
        convert.link(queue)
        queue.link(sink)

class UDPOutCamera(Camera):

    def __init__(self, logger, path, id, name, width, height, framerate, host, port):

        self.host = host
        self.port = port
        super().__init__(logger, None, None, path, id, name, width, height, framerate)

    def create_pipeline(self):
        self.pipeline = Gst.Pipeline.new("pipeline")
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        source = Gst.ElementFactory.make("v4l2src", "camera-source")
        capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        sink = Gst.ElementFactory.make("udpsink", "udpsink")

        self.pipeline.add(source)
        self.pipeline.add(capsfilter)
        self.pipeline.add(convert)
        self.pipeline.add(sink)

        source.set_property("device", self.path)
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string(
                f"video/x-raw, width=${self.width}, height=${self.height}, framerate=${self.framerate}/1"
            ),
        )

        sink.set_property("host", self.host)
        sink.set_property("port", self.port)

        source.link(capsfilter)
        capsfilter.link(convert)
        convert.link(sink)

class UDPCamera(Camera):

    def __init__(self, logger, config_signaller, turn_settings,
                 width, height, framerate, v_format, port, name):

        self.format = v_format
        self.port = port
        super().__init__(logger, config_signaller, turn_settings, f"UDP {port}", None, name, width, height, framerate)

    def create_pipeline(self):
        self.pipeline = Gst.Pipeline.new("pipeline")
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        source = Gst.ElementFactory.make("udpsrc", "udp-source")
        capsfilter = Gst.ElementFactory.make("capsfilter", "filter")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        queue = Gst.ElementFactory.make("queue", "queue")
        sink = Gst.ElementFactory.make("webrtcsink", "webrtc")

        self.pipeline.add(source)
        self.pipeline.add(capsfilter)
        self.pipeline.add(convert)
        self.pipeline.add(queue)
        self.pipeline.add(sink)

        source.set_property("port", self.port)
        caps = Gst.Caps.from_string(f"video/x-raw, format={self.format}, width={self.width}, height={self.height}, framerate={self.framerate}/1")
        capsfilter.set_property("caps", caps)

        sink_config = Gst.Structure.new_empty("meta")
        sink_config.set_value("name", self.name)
        sink.set_property("meta", sink_config)

        if self.turn_settings is not None:
            self.debug(f"Adding TURN-SERVERS to camera {self.turn_settings}")
            sink.set_property("turn-servers",
                              Gst.ValueArray(tuple(self.turn_settings)))

        host = self.config_signaller.host
        if host == "0.0.0.0":
            host = "localhost"

        protocol = "wss" if self.config_signaller.secure == True else "ws"
        uri = f"{protocol}://{host}:{self.config_signaller.port}"

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", uri)

        if self.config_signaller.certificateCA is not None:
            signaller.set_property("cafile",
                                   self.config_signaller.certificateCA)
        

        source.link(capsfilter)
        capsfilter.link(convert)
        convert.link(queue)
        queue.link(sink)

# endregion


class CamerasManager:

    def __init__(self, config: PipelinesConfig,
                 config_signaller: SignallerConfig,
                 turn_settings: Optional[list]):
        self.config = config
        self.config_signaller = config_signaller
        self.turn_settings = turn_settings

        self.cameras = {}
        self.udp_cameras = {}
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
        mode = CameraMode.WebRTC
        udp_host = ""
        udp_port = 0

        if id_path in self.config.cameras:
            camera_config = self.config.cameras[id_path]
            name = camera_config.name
            protocol = camera_config.protocol
            width = camera_config.width
            height = camera_config.height
            framerate = camera_config.framerate
            mode = camera_config.mode

            if mode == CameraMode.UDP:
                udp_host = camera_config.udp.host
                udp_port = camera_config.udp.port

            if camera_config.disable is not None and camera_config.disable:
                self.logger.info(
                    f"skipping camera {name} with id={id_path} path={path} - DISABLED")
                return

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

        if mode == CameraMode.WebRTC:
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
            elif protocol == "raw":
                self.cameras[id_path] = RawCamera(
                    logger=self.logger, config_signaller=self.config_signaller,
                    turn_settings=self.turn_settings, path=path, id=id_path,
                    name=name,
                    width=width, height=height,
                    framerate=framerate
                )
        elif mode == CameraMode.UDP:
            self.cameras[id_path] = UDPOutCamera(
                logger=self.logger, path=path, id=id_path, name=name, width=width, height=height, framerate=framerate, host=udp_host, port=udp_port
            )
            ...

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

    def start_udp_cameras(self):
        for udp in self.config.udp_cameras.values():
            self.udp_cameras[udp.port] = UDPCamera(
                logger=self.logger, config_signaller=self.config_signaller,
                turn_settings=self.turn_settings, width=udp.width, height=udp.height, framerate=udp.framerate, port=udp.port, v_format=udp.format,
                name=udp.name
            )


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
