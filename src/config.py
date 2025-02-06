from typing import Optional

import yaml
from pydantic import FilePath, BaseModel


class SignallerConfig(BaseModel):
    host: str
    port: int
    secure: Optional[bool] = None
    certificate: Optional[FilePath] = None
    certificateCA: Optional[FilePath] = None
    certificatePassword: Optional[str] = None


class Camera(BaseModel):
    name: str
    protocol: str
    width: int
    height: int
    framerate: int


class PipelinesConfig(BaseModel):
    cameras: dict[str, Camera]


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
