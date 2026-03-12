"""
Layer 3 – Calendar Service (Business Logic)

Implements the Sweep Line / Counter algorithm to find every free window
in the working day where ALL requested attendees are simultaneously
available.

UTC-First Policy
----------------
All internal computation (Sweep Line) is performed using UTC-aware
:class:`datetime.datetime` objects.  Working-day boundaries (07:00–19:00)
are enforced **per person in their own timezone**: a slot is only returned
if it falls within 07:00–19:00 for every participant.  *output_tz* controls
the timezone in which the returned (start, end) pairs are expressed.

No I/O is performed here.  The concrete repository is received through
the constructor (Dependency Injection), keeping this class fully
decoupled from storage details.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from io_comp.models import Event, SweepEvent
from io_comp.repository_interface import ICalendarRepository

logger = logging.getLogger(__name__)

# Working-day limits in wall-clock time; applied per person in their own timezone.
_WORKING_START = (7, 0)
_WORKING_END   = (19, 0)

# Host local tz – fixed-offset snapshot adequate for single-day scheduling.
_HOST_TZ = datetime.now(timezone.utc).astimezone().tzinfo


def _person_to_utc(hour: int, minute: int, tz) -> datetime:
    """Combine today with (hour, minute) in *tz* and return a UTC datetime."""
    local_dt = datetime.combine(date.today(), time(hour, minute), tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CalendarService:
    """Finds free meeting slots using a Sweep Line / Counter algorithm.

    **Dependency Injection:** the repository is provided at construction
    time.  CalendarService never instantiates or imports any concrete
    repository class.

    UTC-First: all sweep computation is in UTC; output is converted to
    *output_tz* before being returned.

    Args:
        repository: Any object satisfying :class:`ICalendarRepository`.
        output_tz:  tzinfo used to express the returned (start, end) pairs.
                    Defaults to the host system's current UTC offset.
    """

    def __init__(self, repository: ICalendarRepository, output_tz=None) -> None:
        self._repo = repository
        self._output_tz = output_tz or _HOST_TZ

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sort_available_slots(
        self, person_list: List[str], tz_map: Dict[str, Any] = None
    ) -> List[Tuple[datetime, datetime]]:
        """Return free windows as (start, end) datetime pairs in local timezone.

        All attendees in *person_list* must be simultaneously free for a
        window to be included.  Every non-zero window is returned; callers
        may apply their own minimum-duration filter.

        Args:
            person_list: Names of all required attendees.
            tz_map:      Mapping of person name -> tzinfo.  Used to enforce
                         working-day boundaries (07:00-19:00) in each person's
                         own local time.  Persons absent from the map fall back
                         to *output_tz*.

        Returns:
            List of (start, end) pairs in *output_tz*, sorted by duration
            ascending (ties broken by start time).
            Empty list when no free windows exist.
        """
        if not person_list:
            logger.warning("sort_available_slots called with an empty person_list.")
            return []

        sweep_events = self._build_sweep_events(person_list, tz_map or {})
        utc_slots = self._sweep(sweep_events)

        # Convert UTC results to the output timezone.
        return [
            (s.astimezone(self._output_tz), e.astimezone(self._output_tz))
            for s, e in utc_slots
        ]

    def get_blocking_events(self, person_list: List[str]) -> List[Event]:
        """Return all calendar events belonging to any person in *person_list*."""
        return self._repo.get_events(person_list)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_sweep_events(self, person_list: List[str], tz_map: Dict[str, Any]) -> List[SweepEvent]:
        """Build the sorted list of UTC :class:`SweepEvent` objects.

        Computes the **intersection** of every participant's working window
        (07:00–19:00 in their own timezone) in UTC.  If no such overlap exists
        (e.g. Sydney and New York cannot have a shared window on the same
        calendar day), the list is empty and _sweep returns no slots.

        Calendar events are clamped to the intersection window so that
        meetings outside it cannot produce phantom free windows.
        """
        # ── Step 1: compute each person's working window in UTC ──────────
        working_windows: List[Tuple[datetime, datetime]] = []
        for person in person_list:
            tz = tz_map.get(person, self._output_tz)
            working_windows.append((
                _person_to_utc(*_WORKING_START, tz),
                _person_to_utc(*_WORKING_END,   tz),
            ))

        # ── Step 2: intersection = [latest start, earliest end] ──────────
        intersection_start = max(s for s, _ in working_windows)
        intersection_end   = min(e for _, e in working_windows)

        if intersection_start >= intersection_end:
            logger.warning(
                "No overlapping working window for %s – returning no slots.",
                person_list,
            )
            return []

        # ── Step 3: boundary sweep events ────────────────────────────────
        # A single +1 one minute before the intersection opens ensures the
        # counter is already 1 when the intersection's -1 fires, so that
        # calendar events outside the window (which net to 0) cannot
        # accidentally drop the counter to 0 before the window opens.
        anchor = intersection_start - timedelta(minutes=1)
        events: List[SweepEvent] = [
            SweepEvent(anchor,             +1),  # before window → busy
            SweepEvent(intersection_start, -1),  # window opens  → free
            SweepEvent(intersection_end,   +1),  # window closes → busy
        ]

        # ── Step 4: calendar busy intervals clamped to the window ────────
        for event in self._repo.get_events(person_list):
            ev_start = max(event.start, intersection_start)
            ev_end   = min(event.end,   intersection_end)
            if ev_start < ev_end:
                events.append(SweepEvent(ev_start, +1))
                events.append(SweepEvent(ev_end,   -1))

        return sorted(events)

    def _sweep(
        self, events: List[SweepEvent]
    ) -> List[Tuple[datetime, datetime]]:
        """Run the sweep line; return free-window (start, end) UTC pairs.

        A window is recorded only when end > start.
        Sorted by duration ascending; ties broken by start time.
        """
        counter: int = 0
        free_start: Optional[datetime] = None
        available: List[Tuple[datetime, datetime]] = []

        for sweep_event in events:
            # Counter is about to leave 0 → free window is closing.
            if counter == 0 and sweep_event.event_type == +1:
                if free_start is not None:
                    if sweep_event.at > free_start:
                        available.append((free_start, sweep_event.at))
                free_start = None

            counter += sweep_event.event_type

            # Counter just hit 0 → free window is opening.
            if counter == 0:
                free_start = sweep_event.at

        return sorted(available, key=lambda s: ((s[1] - s[0]), s[0]))
