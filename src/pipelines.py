import time
from logging import Logger
from typing import Optional

import httpx
import psutil

from config import load_signaller_config, load_pipelines_config, \
    load_turn_config, PipelinesConfig, SignallerConfig, TurnConfig
from cameras import CamerasManager
from utils import create_logger

logger: Logger = None
config: PipelinesConfig = None
config_signaller: SignallerConfig = None
config_turn: TurnConfig = None


# region TURN

def get_turn_settings() -> Optional[dict]:
    logger.debug("Requesting TURN credentials")

    headers = {
        "Authorization": f"Bearer {config_turn.apiToken}",
        "Content-Type": "application/json"
    }
    payload = {"ttl": 86400 * 90}

    try:
        with httpx.Client() as client:
            response = client.post(
                config_turn.url.format(
                    TURN_TOKEN=config_turn.turnToken
                ),
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json().get("iceServers", {})
    except httpx.HTTPStatusError as e:
        logger.warning("Cannot get TURN credentials: " + str(e))
        return None
    except httpx.RequestError as e:
        logger.warning("Cannot get TURN credentials: " + str(e))
        return None


def parse_turn_settings(settings):
    servers = []

    if settings is None:
        return None

    username = settings.get("username", "")
    credential = settings.get("credential", "")

    for url in settings.get("urls", []):
        if not url.startswith("turn:") and not url.startswith("turns:"):
            continue

        protocol = url[:url.index(":")]
        host = url[url.index(":") + 1:]

        servers.append(f"{protocol}://{username}:{credential}@{host}")

    logger.debug(f"Parsed TURN settings. Available servers: {servers}")
    return servers


# endregion

# region Signaller

def wait_for_signaller():
    logger.debug("Waiting for signaller")

    found = False
    while not found:
        for connection in psutil.net_connections():
            if connection.laddr.ip == config_signaller.host \
                    and connection.laddr.port == config_signaller.port:
                found = True
                break
        time.sleep(0.1)

    logger.debug("Signaller found!")


# endregion

def main():
    global logger, config, config_signaller, config_turn

    logger = create_logger("pipelines")

    # region Configuration
    config = load_pipelines_config("/configuration/cameras.yaml")
    logger.debug("Pipeline configuration loaded!")

    config_signaller = load_signaller_config("/configuration/signaller.yaml")
    logger.debug("Signaller configuration loaded!")

    config_turn = load_turn_config("/configuration/turn.yaml")
    if config_turn is not None:
        logger.debug("TURN configuration loaded!")
    else:
        logger.warning("Cannot load TURN configuration!")
    # endregion

    # region Turn
    turn_settings = get_turn_settings()
    turn_servers = parse_turn_settings(turn_settings)
    # endregion

    # region Signaller
    wait_for_signaller()
    # endregion

    # region Cameras
    manager = CamerasManager(config, config_signaller, turn_settings)
    manager.detect_cameras()
    manager.start_camera_monitoring()
    # endregion

    # region Active waiting loop
    while True:
        time.sleep(1)
    # endregion


if __name__ == "__main__":
    main()
