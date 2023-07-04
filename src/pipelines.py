import pyudev
import threading
import psutil
import time
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)

context = pyudev.Context()

cameras = {}
cameras_lock = threading.Lock()


class Camera:
    def __init__(self, path, id, name):
        self.path = path
        self.id = id
        self.name = name

        self.log(f"camera created")

        self.start_pipeline()

    def log(self, message):
        print(f"[{self.path}]: {message}")

    def start_pipeline(self):
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
                "video/x-h264, width=1920, height=1080, framerate=25/1"
            ),
        )

        sink_config = Gst.Structure.new_empty("meta")
        sink_config.set_value("display-name", self.name)
        sink.set_property("meta", sink_config)

        source.link(capsfilter)
        capsfilter.link(h264parse)
        h264parse.link(avdec_h264)
        avdec_h264.link(sink)

        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        self.log("stream started")

    def restart_pipeline(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
        self.log("stream restarted")

    def stop_pipeline(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

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


def wait_for_signaller():
    print("waiting for signaller...")
    while True:
        for connection in psutil.net_connections():
            if connection.laddr.ip == "0.0.0.0" and connection.laddr.port == 8443:
                return
        time.sleep(0.1)


def add_camera(device):
    global cameras

    id = device.get("ID_PATH")
    default_name = device.get("ID_PATH_TAG")
    path = device.device_node
    serial = device.get("ID_SERIAL_SHORT")
    vendor = device.get("ID_VENDOR")
    model = device.get("ID_MODEL")

    print(f"adding camera {id} = {path}")

    cameras[id] = Camera(path, id, default_name)


def remove_camera(device):
    global cameras

    id = device.get("ID_PATH")
    print(f"removing camera {id}")

    cameras[id].stop_pipeline()
    del cameras[id]

    print(cameras)


def get_cameras():
    global cameras
    global cameras_lock
    global context

    cameras_lock.acquire(blocking=True)
    print("getting cameras")
    for device in context.list_devices(
        subsystem="video4linux", ID_V4L_CAPABILITIES=":capture:"
    ):
        # for property in device.properties:
        #    print(f"{property} = {device.get(property)}")
        add_camera(device)

    cameras_lock.release()


def init_camera_monitoring():
    global cameras
    global cameras_lock
    global context

    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("video4linux")

    def log_event(action, device):
        if device.get("ID_V4L_CAPABILITIES") == ":capture:":
            print(action, device, device.get("ID_PATH"))
            if action == "add":
                cameras_lock.acquire(blocking=True)
                add_camera(device)
                cameras_lock.release()
            elif action == "remove":
                cameras_lock.acquire(blocking=True)
                remove_camera(device)
                cameras_lock.release()
            else:
                print(action, device)

    observer = pyudev.MonitorObserver(monitor, log_event)
    observer.start()


wait_for_signaller()
get_cameras()
init_camera_monitoring()

while True:
    pass
