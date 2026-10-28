"""Contracts package for inter-service communication between core-api and agent-service."""

from .envelope import APIError, UniformEnvelope
from .agent import (
    AgentChatRequest,
    AgentChatResponse,
    PersonalizationContext,
    Principal,
    HistoryTurn,
)
from .health import (
    BmiRequest,
    BmiResult,
    PbfRequest,
    PbfResult,
    VisceralFatRequest,
    VisceralFatResult,
    NutritionRequest,
    NutritionResult,
    TrainingRequest,
    TrainingResult,
    SafetyRequest,
    SafetyResult,
)

__all__ = [
    "UniformEnvelope",
    "APIError",
    "Principal",
    "PersonalizationContext",
    "HistoryTurn",
    "AgentChatRequest",
    "AgentChatResponse",
    "BmiRequest",
    "BmiResult",
    "PbfRequest",
    "PbfResult",
    "VisceralFatRequest",
    "VisceralFatResult",
    "NutritionRequest",
    "NutritionResult",
    "TrainingRequest",
    "TrainingResult",
    "SafetyRequest",
    "SafetyResult",
]
