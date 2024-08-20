import logging
import threading
import time

import gi
import httpx
import psutil
import pyudev
import yaml


# Setup Logger
logFormatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

fileHandler = logging.FileHandler("pipeline.log")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)


# Setup GStreamer
gi.require_version("Gst", "1.0")
from gi.repository import Gst
Gst.init(None)

# Setup pyudev
udev_context = pyudev.Context()

# Setup cameras
cameras = {}
cameras_lock = threading.Lock()
config = {}

signaller_uri = "wss://localhost:8443"
signaller_cafile = "/certificates/RootCA.pem"


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
        logger.info(f"[{self.path}]: {message}")

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
        self.stop_pipeline()
        self.start_pipeline()
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
        sink_config.set_value("name", self.name)
        sink.set_property("meta", sink_config)
        sink.set_property("turn-servers", turns)

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", signaller_uri)
        signaller.set_property("cafile", signaller_cafile)

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
        sink.set_property("turn-servers", turns)

        signaller = sink.get_property("signaller")
        signaller.set_property("uri", signaller_uri)
        signaller.set_property("cafile", signaller_cafile)

        source.link(capsfilter)
        capsfilter.link(jpegdec)
        jpegdec.link(sink)


def add_camera(device):
    logger.debug("Add camera {debug}")
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
        logger.info(f"adding camera {name} with id={id} path={path}")
    else:
        logger.info(f"adding unknown camera with id={id} path={path}")
        logger.info(f"used config:")
        logger.info(
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


def get_turn_credentials():
    headers = {
        "Authorization": f"Bearer {config.get("apiToken", "")}",
        "Content-Type": "application/json"
    }
    payload = {"ttl": 86400 * 90}
    
    try:
        with httpx.Client() as client:
            response = client.post(
                config.get("url", "").format(TURN_TOKEN=config.get("turnToken", "")),
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json().get("iceServers")
    except httpx.HTTPStatusError as e:
        return None
    except httpx.RequestError as e:
        return None
    
    
def process_turn_settings():
    credentials = get_turn_credentials()
    servers = []
    
    if credentials is None:
        return None
    
    user = credentials.get("username", "")
    password = credentials.get("credential", "")
    
    for url in credentials.get("urls", []):
        if not url.startswith("turn:"):
            continue
        
        protocol = url[:url.index(":")]
        host = url[url.index(":") + 1:]
        
        servers.append(f"{protocol}://{user}:{password}@{host}")
        
    logger.debug(f"TURN Servers: {servers}")
    return servers


def remove_camera(device):
    logging.debug("Remove camera {device}")
    global cameras

    id = device.get("ID_PATH")

    cameras_lock.acquire(blocking=True)

    logger.info(f"removing camera {cameras[id].name} with id={id} path={cameras[id].path}")
    cameras[id].stop_pipeline()
    del cameras[id]

    cameras_lock.release()


def get_cameras():
    logging.debug("Get cameras")
    global cameras
    global cameras_lock
    global udev_context

    logger.info("getting cameras")
    for device in udev_context.list_devices(
        subsystem="video4linux", ID_V4L_CAPABILITIES=":capture:"
    ):
        # for property in device.properties:
        #    logger.info(f"{property} = {device.get(property)}")
        add_camera(device)

    logging.debug("Cameras discovered")

def init_camera_monitoring():
    logger.debug("Init camera monitoring")

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
                logger.info(action, device)

    observer = pyudev.MonitorObserver(monitor, log_event)
    logger.debug("Start observer")
    observer.start()


def wait_for_signaller():
    logger.debug("Wait for signaller")

    logger.info("waiting for signaller...")
    while True:
        for connection in psutil.net_connections():
            if connection.laddr.ip == "0.0.0.0" and connection.laddr.port == 8443:
                return
        time.sleep(0.1)

    logger.debug("Signaller found!")


def load_config():
    logger.debug("Load configuration")

    global config
    with open("/configuration/cameras/config.yml", "r") as stream:
        config = yaml.safe_load(stream)
        
    global turns
    turns = process_turn_settings()

    logger.info("Configuration loaded!")

if __name__ == "__main__":
    load_config()
    wait_for_signaller()
    get_cameras()
    init_camera_monitoring()

    while True:
        time.sleep(1)
