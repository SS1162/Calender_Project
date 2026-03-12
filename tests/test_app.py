"""
Unit tests for the Comp calendar scheduler.

A lightweight in-memory stub repository (StubCalendarRepository) is
injected into CalendarService so tests run without touching the filesystem.
This is the Dependency Injection pattern for testability: the stub satisfies
the ICalendarRepository structural protocol by exposing get_events().

Timezone note
-------------
All tests use UTC as both the data timezone and the output timezone
(local_tz=UTC).  This makes assertions independent of the machine's local
clock offset: a time of 07:00 UTC in → 07:00 UTC out, no conversion.
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Tuple

from io_comp import CalendarService
from io_comp.models import Event

UTC = timezone.utc
_TODAY = date.today()


def _dt(hour: int, minute: int) -> datetime:
    """UTC-aware datetime for today at hour:minute (used in all assertions)."""
    return datetime(_TODAY.year, _TODAY.month, _TODAY.day, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Test double – in-memory stub satisfying ICalendarRepository
# ---------------------------------------------------------------------------


class StubCalendarRepository:
    """In-memory repository used exclusively in tests.

    Accepts a list of (person, start_dt, end_dt) tuples where start/end are
    UTC-aware datetime objects, matching the Event schema after the UTC-first
    policy was introduced.
    """

    def __init__(self, intervals: List[Tuple[str, datetime, datetime]]) -> None:
        self._events: List[Event] = [
            Event(person=person, subject="stub", start=start, end=end)
            for person, start, end in intervals
        ]

    def get_events(self, person_list: List[str]) -> List[Event]:
        person_set = set(person_list)
        return [e for e in self._events if e.person in person_set]


def _make_service(
    intervals: List[Tuple[str, datetime, datetime]],
) -> Tuple[CalendarService, dict]:
    """Build a CalendarService backed by an in-memory stub repository.

    Every person is assigned UTC as their timezone so test assertions are
    timezone-agnostic (07:00 UTC in -> 07:00 UTC out, no conversion).
    Returns (service, tz_map) so callers can pass tz_map to sort_available_slots.
    """
    tz_map = {p: UTC for p, _, _ in intervals}
    return CalendarService(StubCalendarRepository(intervals), output_tz=UTC), tz_map


# ---------------------------------------------------------------------------
# Test 1 – Boundary: person with no events is free the whole working day
# ---------------------------------------------------------------------------


def test_single_free_person_returns_full_day_window():
    """A person with zero events yields exactly one slot: 07:00–19:00."""
    service, tz_map = _make_service([])  # no busy intervals at all
    slots = service.sort_available_slots(["Alice"], tz_map=tz_map)

    assert len(slots) == 1
    assert slots[0] == (_dt(7, 0), _dt(19, 0)), "Slot must span the full working day"


# ---------------------------------------------------------------------------
# Test 2 – Two attendees with overlapping/adjacent events
# ---------------------------------------------------------------------------


def test_two_persons_correct_free_windows():
    """Verify the sweep finds the right gaps for Alice and Jack, sorted by duration.

    Schedule:
        Alice: 08:00-09:30, 13:00-14:00, 16:00-17:00
        Jack : 08:00-08:50, 09:00-09:40, 13:00-14:00, 16:00-17:00

    Free windows sorted by duration ascending:
        07:00 → 08:00   (60 min)   ← shortest
        14:00 → 16:00  (120 min)   tie – earlier start first
        17:00 → 19:00  (120 min)   tie
        09:40 → 13:00  (200 min)   ← longest
    """
    intervals = [
        ("Alice", _dt(8, 0),  _dt(9, 30)),
        ("Alice", _dt(13, 0), _dt(14, 0)),
        ("Alice", _dt(16, 0), _dt(17, 0)),
        ("Jack",  _dt(8, 0),  _dt(8, 50)),
        ("Jack",  _dt(9, 0),  _dt(9, 40)),
        ("Jack",  _dt(13, 0), _dt(14, 0)),
        ("Jack",  _dt(16, 0), _dt(17, 0)),
    ]
    service, tz_map = _make_service(intervals)
    slots = service.sort_available_slots(["Alice", "Jack"], tz_map=tz_map)

    assert slots == [
        (_dt(7, 0),  _dt(8, 0)),    # 60 min
        (_dt(14, 0), _dt(16, 0)),   # 120 min
        (_dt(17, 0), _dt(19, 0)),   # 120 min
        (_dt(9, 40), _dt(13, 0)),   # 200 min
    ]


# ---------------------------------------------------------------------------
# Test 3 – Back-to-back busy periods produce no phantom free window
# ---------------------------------------------------------------------------


def test_adjacent_busy_periods_no_phantom_window():
    """Two consecutive busy intervals with no gap between them must NOT
    create a zero-length free window at the junction point."""
    intervals = [
        ("Alice", _dt(7, 0),  _dt(10, 0)),  # 07:00-10:00 busy
        ("Alice", _dt(10, 0), _dt(19, 0)),  # 10:00-19:00 busy  (adjacent)
    ]
    service, tz_map = _make_service(intervals)
    slots = service.sort_available_slots(["Alice"], tz_map=tz_map)

    assert slots == [], "Adjacent busy periods with no gap must yield no slots."


# ---------------------------------------------------------------------------
# Test 4 – Whole day blocked → no slots
# ---------------------------------------------------------------------------


def test_no_slots_when_fully_booked():
    """A person booked from 07:00 to 19:00 leaves no available slots."""
    intervals = [("Bob", _dt(7, 0), _dt(19, 0))]
    service, tz_map = _make_service(intervals)
    slots = service.sort_available_slots(["Bob"], tz_map=tz_map)

    assert slots == []


# ---------------------------------------------------------------------------
# Test 5 – Person absent from calendar is treated as fully free
# ---------------------------------------------------------------------------


def test_unknown_person_treated_as_free():
    """A person with no data in the repository is free the whole day."""
    service, tz_map = _make_service([])  # empty repository
    slots = service.sort_available_slots(["Ghost"], tz_map=tz_map)

    assert len(slots) == 1
    assert slots[0] == (_dt(7, 0), _dt(19, 0))


# ---------------------------------------------------------------------------
# Test 6 – Results are always sorted earliest → latest
# ---------------------------------------------------------------------------


def test_slots_are_sorted_by_duration_ascending():
    """sort_available_slots must return (start, end) pairs shortest-to-longest."""
    intervals = [
        ("Alice", _dt(8, 0),  _dt(9, 0)),
        ("Alice", _dt(11, 0), _dt(12, 0)),
        ("Alice", _dt(15, 0), _dt(16, 0)),
    ]
    service, tz_map = _make_service(intervals)
    slots = service.sort_available_slots(["Alice"], tz_map=tz_map)
    # Free windows: 07:00-08:00=60min, 09:00-11:00=120min, 12:00-15:00=180min, 16:00-19:00=180min
    durations = [(end - start) for start, end in slots]
    assert durations == sorted(durations), "Slots must be sorted by duration ascending."
