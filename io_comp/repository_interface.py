"""
Layer 2 – Repository Interface

Defines the *port* (Protocol) that any calendar data-source must satisfy.
Keeping the interface in its own file lets the service layer import only
this module, with zero coupling to concrete storage implementations.
"""

from typing import List, Protocol, runtime_checkable

from io_comp.models import Event


@runtime_checkable
class ICalendarRepository(Protocol):
    """Read-only port for calendar event storage.

    Any class that exposes a ``get_events()`` method returning
    ``List[Event]`` satisfies this structural sub-type and can be
    injected into ``CalendarService`` without explicit inheritance.

    Examples of conforming classes:
        * ``CSVCalendarRepository`` – loads from a CSV file.
        * ``StubCalendarRepository`` – in-memory stub for unit tests.
        * A future ``DatabaseCalendarRepository`` – loads from a DB.
    """

    def get_events(self, person_list: List[str]) -> List[Event]:
        """Return calendar events for the given people only.

        The repository is responsible for the filtering so that a
        DB-backed implementation can push a ``WHERE person IN (...)
        `` clause to the database instead of loading the full dataset.

        Args:
            person_list: Names of the people whose events are needed.

        Returns:
            A list of :class:`Event` objects for those people only.
            Must never return ``None``; return an empty list instead.
        """
        ...
