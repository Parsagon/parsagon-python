class ParsagonException(Exception):
    """Base class for all exceptions in Parsagon. The CLI will use the to_string method to print the exception to the user."""

    def to_string(self, verbose):
        return str(self)

    def __str__(self):
        return self.to_string(True)


class APIException(ParsagonException):
    def __init__(self, value):
        super().__init__(value)
        self.value = value

    def to_string(self, verbose):
        return self.value


class ProgramNotFoundException(ParsagonException):
    """Raised when a program specified by name or ID is not found."""

    def __init__(self, program):
        super().__init__(program)
        self.program = program

    def to_string(self, verbose):
        return f"A program with name {self.program} does not exist."
