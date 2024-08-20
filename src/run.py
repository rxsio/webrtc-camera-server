import logging
import os
import subprocess
import signal

import yaml


CERT = "/certificates/firo.p12"
CERT_PASSWORD = "skar"

# Setup Logger
logFormatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

fileHandler = logging.FileHandler("run.log")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)


def create_signaller():
    env = os.environ.copy()
    env['WEBRTCSINK_SIGNALLING_SERVER_LOG'] = 'debug'
    env['GST_PLUGIN_PATH'] = '/gst-plugins-rs/target/release:' + os.environ['GST_PLUGIN_PATH']
     
    command = [
        './gst-plugins-rs/target/release/gst-webrtc-signalling-server',
        '--cert', CERT,
        '--cert-password', CERT_PASSWORD
    ]
    
    process = subprocess.Popen(command)
    
    try:
        
        process.wait()
    except:
        process.send_signal(signal.SIGINT)
        process.wait()


def load_config():
    logger.debug("Load configuration")

    global config
    with open("/configuration/cameras/turn.yml", "r") as stream:
        config = yaml.safe_load(stream)

    logger.info("Configuration loaded!")


if __name__ == "__main__":
    load_config()
    create_signaller()
