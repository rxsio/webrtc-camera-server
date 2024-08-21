from typing import Optional

import yaml
from pydantic import FilePath, BaseModel


class SignallerConfig(BaseModel):
    host: str
    port: int
    certificate: Optional[FilePath] = None
    certificatePassword: Optional[str] = None


class PipelinesConfig(BaseModel):
    ...


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
