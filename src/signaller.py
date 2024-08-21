import os
import signal
import subprocess

from config import load_signaller_config, SignallerConfig


def create_signaller(config: SignallerConfig):
    env = os.environ.copy()
    env["WEBRTCSINK_SIGNALLING_SERVER_LOG"] = "debug"
    env["GST_PLUGIN_PATH"] = "/gst-plugins-rs/target/release:" + os.environ[
        "GST_PLUGIN_PATH"]

    command = [
        "./gst-plugins-rs/target/release/gst-webrtc-signalling-server",
        "--host", config.host,
        "--port", config.port,

    ]

    if config.certificate is not None:
        command.extend([
            "--cert", config.certificate,
            "--cert-password", config.certificatePassword
        ])

    process = subprocess.Popen(command, env=env)

    try:
        process.wait()
    except:
        process.send_signal(signal.SIGINT)
        process.wait()


def main():
    config = load_signaller_config("/configuration/signaller.yaml")
    create_signaller(config)


if __name__ == "__main__":
    main()
