from typing import Optional
from enum import Enum

import yaml
from pydantic import FilePath, BaseModel


class SignallerConfig(BaseModel):
    host: str
    port: int
    secure: Optional[bool] = None
    certificate: Optional[FilePath] = None
    certificateCA: Optional[FilePath] = None
    certificatePassword: Optional[str] = None


class CameraMode(str, Enum):
    WebRTC = "webrtc"
    UDP = "udp"

class UDPSettings(BaseModel):
    host: str
    port: int

class Camera(BaseModel):
    name: str
    protocol: str
    width: int
    height: int
    framerate: int
    disable: Optional[bool] = None
    mode: CameraMode = CameraMode.WebRTC
    udp: Optional[UDPSettings] = None

class UDPCamera(BaseModel):
    name: str
    width: int
    height: int
    framerate: int
    port: int
    format: str


class PipelinesConfig(BaseModel):
    cameras: dict[str, Camera]
    udp_cameras: dict[str, UDPCamera] = {}


class TurnConfig(BaseModel):
    url: str
    apiToken: str
    turnToken: str


def load_signaller_config(filepath: FilePath) -> SignallerConfig:
    with open(filepath, 'r') as handle:
        data = yaml.safe_load(handle)

    return SignallerConfig(**data)


def load_pipelines_config(filepath: FilePath) -> PipelinesConfig:
    with open(filepath, 'r') as handle:
        data = yaml.safe_load(handle)

    return PipelinesConfig(**data)


def load_turn_config(filepath: FilePath) -> Optional[TurnConfig]:
    try:
        with open(filepath, "r") as handle:
            data = yaml.safe_load(handle)

        return TurnConfig(**data)
    except:
        return None
