"""
Domain Exceptions

Custom exception hierarchy for the calendar application.
Raising domain-specific exceptions lets callers catch exactly the errors
they care about without accidentally swallowing unrelated built-in errors.
"""


class CalendarFileNotFoundError(FileNotFoundError):
    """Raised when the calendar CSV file cannot be found.

    Inherits from :class:`FileNotFoundError` so existing ``except
    FileNotFoundError`` clauses remain compatible.
    """

    def __init__(self, filepath: str) -> None:
        super().__init__(f"Calendar file not found: '{filepath}'")
        self.filepath = filepath


class InvalidEventError(ValueError):
    """Raised when a CSV row contains unparseable or logically invalid event data.

    Inherits from :class:`ValueError` so existing ``except ValueError``
    clauses remain compatible.
    """

    def __init__(self, message: str, line_num: int = None, filepath: str = None) -> None:
        location = ""
        if filepath and line_num:
            location = f" (file '{filepath}', row {line_num})"
        elif line_num:
            location = f" (row {line_num})"
        super().__init__(f"Invalid event data{location}: {message}")
        self.line_num = line_num
        self.filepath = filepath
