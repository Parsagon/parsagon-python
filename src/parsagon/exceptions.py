class ParsagonException(Exception):
    """Base class for all exceptions in Parsagon. The CLI will use the to_string method to print the exception to the user."""

    def to_string(self, verbose):
        return str(self)


class APIException(ParsagonException):
    def __init__(self, value, status_code):
        super().__init__(value)
        self.value = value
        self.status_code = status_code

    def to_string(self, verbose):
        return f"{self.status_code} - {self.value}"


class ProgramNotFoundException(ParsagonException):
    """Raised when a program specified by name or ID is not found."""

    def __init__(self, program):
        super().__init__(program)
        self.program = program

    def to_string(self, verbose):
        return f"A program with name {self.program} does not exist."


class RunFailedException(ParsagonException):
    """Raised when a run fails."""
    pass
