"""Structured validation failures independent of translated display messages."""


class ValidationError(ValueError):
    def __init__(self, message, field_name=None, code="invalid_input"):
        super().__init__(message)
        self.field_name = field_name
        self.code = code


InputError = ValidationError  # Compatibility for existing model callers.
