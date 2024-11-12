import yaml

class KObject():
  def __init__(self, apiVersion: str, kind: str, name: str) -> None:
    self.apiVersion = apiVersion
    self.kind = kind
    self.metadata = {
      "name": name,
      "labels": {},
      "annotations": {}
    }
  def __str__(self) -> str:
    return yaml.dump(self.__dict__)

class KIterable():
  """Kubernetes Iterable
  
  A mixin to make a Kubernetes object an iterable class.
  This means the object has an 'items' key with an array
  of resources. 
  """
  def __iter__(self):
    self._items = iter(self.items)
    return self
  def __next__(self):
    return next(self._items)

class ResourceList(KObject, KIterable):
  def __init__(self, functionConfig = {}, items = []) -> None:
    super().__init__(
      apiVersion="config.kubernetes.io/v1",
      kind="ResourceList",
      name="cubizoid"
    )
    self.items = items
    self.functionConfig = functionConfig
