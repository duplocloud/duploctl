
class DuploError(Exception):
  """Base class for Duplo errors."""
  def __init__(self, message, code=1, response=None):
    super().__init__(message)
    self.message = message
    self.code = code
    self.response = response
  def __str__(self):
    return f"{self.code}: {self.message}"

class DuploExpiredCache(DuploError):
  """Raised when the Duplo cache is expired."""
  def __init__(self, key: str):
    self.key = key
    super().__init__("Cache item {key} is expired", 404)
