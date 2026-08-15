from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    READ = "read"
    WAIT = "wait"


class LocatorStrategy(str, Enum):
    ROLE = "role"
    LABEL = "label"
    TEXT = "text"
    CSS = "css"


class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


class OutputType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


class Locator(BaseModel):
    strategy: LocatorStrategy
    value: str


class InputParameter(BaseModel):
    name: str
    type: ParameterType
    required: bool = True
    description: Optional[str] = None


class OutputField(BaseModel):
    name: str
    type: OutputType
    description: Optional[str] = None


class Step(BaseModel):
    id: str
    action: ActionType
    locator: Optional[Locator] = None
    value: Optional[str] = None
    output_name: Optional[str] = None
    description: Optional[str] = None


class Checkpoint(BaseModel):
    locator: Locator
    expected_text: Optional[str] = None
    description: Optional[str] = None


class CapabilityArtifact(BaseModel):
    artifact_version: str = Field(default="1.0")
    capability_name: str
    description: str
    target: str

    inputs: List[InputParameter]
    outputs: List[OutputField]

    steps: List[Step]

    checkpoint: Checkpoint

    metadata: Dict[str, Any] = Field(default_factory=dict)