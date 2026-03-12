"""
Layer 3 – Calendar Service Interface

Defines the *port* (Protocol) that any calendar-service implementation
must satisfy.  Keeping the interface in its own file mirrors the pattern
used by ICalendarRepository and lets callers (e.g. app.py, tests) depend
on the abstraction rather than on the concrete CalendarService class.

Examples of conforming classes:
    * ``CalendarService``      – production sweep-line implementation.
    * A future stub/mock class – for integration or end-to-end tests.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from io_comp.models import Event


@runtime_checkable
class ICalendarService(Protocol):
    """Port for calendar scheduling logic.

    Any class that exposes ``sort_available_slots`` and
    ``get_blocking_events`` with the signatures below satisfies this
    structural sub-type and can be injected wherever an
    ``ICalendarService`` is expected – without explicit inheritance.
    """

    def sort_available_slots(
        self,
        person_list: List[str],
        tz_map: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[datetime, datetime]]:
        """Return free windows where all attendees are simultaneously free.

        Args:
            person_list: Names of all required attendees.
            tz_map:      Mapping of person name -> tzinfo.  Working-day
                         boundaries (07:00-19:00) are enforced in each
                         person's own local timezone.  Persons absent from
                         the map fall back to the implementation's output_tz.

        Returns:
            List of (start, end) pairs sorted by duration ascending.
            Empty list when no free windows exist.
        """
        ...

    def get_blocking_events(self, person_list: List[str]) -> List[Event]:
        """Return all calendar events belonging to any person in *person_list*.

        Args:
            person_list: Names of the people whose events are needed.

        Returns:
            List of :class:`Event` objects for those people.
        """
        ...
