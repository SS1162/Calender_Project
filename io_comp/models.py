"""
Layer 1 – Domain Models

Immutable dataclasses that represent the core business objects.
No I/O, no business logic – pure data.

All datetime fields are **timezone-aware UTC** datetime objects.
The repository layer is responsible for converting local times to UTC
before constructing these objects.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """An immutable calendar event belonging to one person.

    Attributes:
        person:  Name of the person who owns this event.
        subject: Human-readable title of the event.
        start:   UTC-aware datetime when the event begins.
        end:     UTC-aware datetime when the event ends.
    """

    person: str
    subject: str
    start: datetime   # timezone-aware UTC datetime
    end: datetime     # timezone-aware UTC datetime

    def __post_init__(self) -> None:
        if self.start >= self.end:
            logger.warning(
                "Event '%s' for %s has start=%s >= end=%s; this may cause unexpected results.",
                self.subject,
                self.person,
                self.start,
                self.end,
            )


@dataclass(frozen=True, order=True)
class SweepEvent:
    """A point-event on the sweep-line timeline.

    Using a dataclass with ``order=True`` makes sorting trivial:
    Python compares fields left-to-right, so at equal *at* times
    ``event_type=-1`` (end) sorts before ``event_type=+1`` (start).
    This prevents back-to-back busy periods from generating a spurious
    zero-counter window.

    Attributes:
        at:          UTC-aware datetime when this event occurs.
        event_type:  +1 = busy interval begins, -1 = busy interval ends.
    """

    at: datetime       # primary sort key (UTC-aware datetime)
    event_type: int    # -1 < +1  →  ends sort before starts on ties
