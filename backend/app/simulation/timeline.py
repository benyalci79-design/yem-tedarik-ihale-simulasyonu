from dataclasses import dataclass
from decimal import Decimal

# Otomatik değerlendirme kaldırıldı; karar kullanıcıya ait. Teslimat her zaman
# diğer olaylardan önce işlenir, ardından NPC cevabı ve ihale kapanışı gelir.
EVENT_PRIORITY = {
    "delivery": 0,
    "response": 2,
    "close": 3,
}


@dataclass(frozen=True)
class TimelineEvent:
    at_seconds: Decimal
    kind: str
    object_id: int


def ordered_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Aynı anda olayları işlem sırasına göre düzenler."""
    return sorted(events, key=lambda event: (event.at_seconds, EVENT_PRIORITY[event.kind], event.object_id))
