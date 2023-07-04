import pyudev
import threading
import psutil
import yaml
import time
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)

udev_context = pyudev.Context()

cameras = {}
cameras_lock = threading.Lock()
config = {}


class Camera:
    def __init__(self, path, id, name, width, height, framerate):
        self.path = path
        self.id = id
        self.name = name

        self.width = width
        self.height = height
        self.framerate = framerate

        self.log(f"camera created")

        self.create_pipeline()
        self.start_pipeline()

    def log(self, message):
        print(f"[{self.path}]: {message}")

    def create_pipeline(self):
        raise NotImplementedError()

    def start_pipeline(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        self.log("stream started")

    def stop_pipeline(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

    def restart_pipeline(self):
        self.start_pipeline()
        self.stop_pipeline()
        self.log("stream restarted")

    def on_message(self, bus, message):
        self.log(message)
        t = message.type
        if t == Gst.MessageType.EOS:
            self.log("stream ended")
            self.restart_pipeline()
        elif t == Gst.MessageType.ERROR:
            self.player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            self.log(f"stream error {err} {debug}")
            self.restart_pipeline()

    def __del__(self):
        self.stop_pipeline()
        self.log(f"camera destroyed")


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
        sink_config.set_value("display-name", self.name)
        sink.set_property("meta", sink_config)

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
        sink_config.set_value("display-name", self.name)
        sink.set_property("meta", sink_config)

        source.link(capsfilter)
        capsfilter.link(jpegdec)
        jpegdec.link(sink)


def add_camera(device):
    global cameras
    global config

    id = device.get("ID_PATH")
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

    if config["cameras"] is not None and id in config["cameras"]:
        camera_config = config["cameras"][id]
        name = camera_config["name"]
        protocol = camera_config["protocol"]
        width = camera_config["width"]
        height = camera_config["height"]
        framerate = camera_config["framerate"]
        print(f"adding camera {name} with id={id} path={path}")
    else:
        print(f"adding unknown camera with id={id} path={path}")
        print(f"used config:")
        print(
            yaml.dump(
                {
                    "cameras": {
                        id: {
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

    cameras_lock.acquire(blocking=True)
    if protocol == "h264":
        cameras[id] = H264Camera(
            path=path, id=id, name=name, width=width, height=height, framerate=framerate
        )
    elif protocol == "mjpeg":
        cameras[id] = MJPEGCamera(
            path=path, id=id, name=name, width=width, height=height, framerate=framerate
        )

    cameras_lock.release()


def remove_camera(device):
    global cameras

    id = device.get("ID_PATH")

    cameras_lock.acquire(blocking=True)

    print(f"removing camera {cameras[id].name} with id={id} path={cameras[id].path}")
    cameras[id].stop_pipeline()
    del cameras[id]

    cameras_lock.release()


def get_cameras():
    global cameras
    global cameras_lock
    global udev_context

    print("getting cameras")
    for device in udev_context.list_devices(
        subsystem="video4linux", ID_V4L_CAPABILITIES=":capture:"
    ):
        # for property in device.properties:
        #    print(f"{property} = {device.get(property)}")
        add_camera(device)


def init_camera_monitoring():
    global cameras
    global cameras_lock
    global udev_context

    monitor = pyudev.Monitor.from_netlink(udev_context)
    monitor.filter_by("video4linux")

    def log_event(action, device):
        if device.get("ID_V4L_CAPABILITIES") == ":capture:":
            if action == "add":
                add_camera(device)
            elif action == "remove":
                remove_camera(device)
            else:
                print(action, device)

    observer = pyudev.MonitorObserver(monitor, log_event)
    observer.start()


def wait_for_signaller():
    print("waiting for signaller...")
    while True:
        for connection in psutil.net_connections():
            if connection.laddr.ip == "0.0.0.0" and connection.laddr.port == 8443:
                return
        time.sleep(0.1)


def load_config():
    global config
    with open("/config.yaml", "r") as stream:
        config = yaml.safe_load(stream)


if __name__ == "__main__":
    load_config()
    wait_for_signaller()
    get_cameras()
    init_camera_monitoring()

    while True:
        pass
