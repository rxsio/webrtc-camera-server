import os
import signal
import subprocess

from config import load_signaller_config, SignallerConfig


def create_signaller(config: SignallerConfig):
    env = os.environ.copy()
    env["WEBRTCSINK_SIGNALLING_SERVER_LOG"] = "debug"

    gst_plugin_path = "/gst-plugins-rs/target/release"
    if "GST_PLUGIN_PATH" in os.environ:
        gst_plugin_path = gst_plugin_path + ":" + os.environ["GST_PLUGIN_PATH"]
    env["GST_PLUGIN_PATH"] = gst_plugin_path

    command = [
        "./gst-plugins-rs/target/release/gst-webrtc-signalling-server",
        "--host", config.host,
        "--port", str(config.port),

    ]

    if config.certificate is not None:
        command.extend([
            "--cert", config.certificate,
            "--cert-password", config.certificatePassword
        ])

    with open("signaller.log", "w") as handle:
        process = subprocess.Popen(
            [str(elem) for elem in command], 
            env=env,
            text=True,
            stdout=handle,
            stderr=handle
        )

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
