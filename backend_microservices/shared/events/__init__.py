from .schemas import (
    SlotStatus,
    EventEnvelope,
    DetectionCompletedPayload,
    ParkingSlotUpdatedPayload,
    ParkingSessionStartedPayload,
    ParkingSessionCompletedPayload,
    BillingCompletedPayload
)
import importlib


def get_publisher():
    from .publisher import get_publisher as _get_publisher

    return _get_publisher()


def __getattr__(name: str):
    if name in {"EventPublisher", "publisher"}:
        publisher_module = importlib.import_module(".publisher", __name__)
        return getattr(publisher_module, name)
    raise AttributeError(name)

__all__ = [
    "SlotStatus",
    "EventEnvelope",
    "DetectionCompletedPayload",
    "ParkingSlotUpdatedPayload",
    "ParkingSessionStartedPayload",
    "ParkingSessionCompletedPayload",
    "BillingCompletedPayload",
    "EventPublisher",
    "get_publisher",
    "publisher"
]
