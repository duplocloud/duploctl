
class DuploError(Exception):
    """Base class for Duplo errors."""
    def __init__(self, message, code=1, response=None):
        super().__init__(message)
        self.code = code
        self.response = response
    def __str__(self):
        return f"{self.code}: {self.message}"