"""facade de compatibilidade; implementação em suricata/legacy/."""

from .legacy.delivery import Delivery, DeliveryError, DeliveryOrchestrator

__all__ = ["Delivery", "DeliveryError", "DeliveryOrchestrator"]
