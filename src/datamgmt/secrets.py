import yaml
import os
from log.logger import *

class Secrets:
  @classmethod
  def shared(cls):
    if not hasattr(cls, "_shared"):
      cls._shared = Secrets()
    return cls._shared
  
  def __init__(self, path=None):
    self.path = "secrets.yaml"
    self.load()

  def load(self):
    if not os.path.exists(self.path):
      raise FileNotFoundError(f"Cannot find secrets file at {self.path}")
    
    with open(self.path, "r") as f:
      self.secrets = yaml.safe_load(f)

  def get(self, key):
    if not key in self.secrets:
      log_critical(f"No such key in secrets: {key}")
      return None
    return self.secrets[key]
  
def secret(key):
  return Secrets.shared().get(key)
