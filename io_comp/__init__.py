"""
Comp Calendar Exercise – Python Implementation
===============================================

Layer 4 – Public API  (this file)

Re-exports the public symbols from each inner layer so callers can do::

    from io_comp import CalendarService, CSVCalendarRepository, Event

For wiring and execution, see ``app.py`` (composition root).
"""

from io_comp.csv_repository import CSVCalendarRepository
from io_comp.models import Event, SweepEvent
from io_comp.repository_interface import ICalendarRepository
from io_comp.service import CalendarService
from io_comp.service_interface import ICalendarService

__all__ = [
    "CalendarService",
    "CSVCalendarRepository",
    "Event",
    "ICalendarRepository",
    "ICalendarService",
    "SweepEvent",
]






