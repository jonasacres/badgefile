import os
from .log_target import LogTarget

class Textfile(LogTarget):
  def __init__(self, path):
    super().__init__()
    self.path = path
    
    # Handle case where path has no directory component
    dirpath = os.path.dirname(path)
    if dirpath:
      os.makedirs(dirpath, exist_ok=True)
    self.file = open(path, 'a')

  def log_msg(self, info):
    self.file.write("[%s] %s %30s: %s\n" % (
                            info["severity_str_short"],
                            info["timestamp_str"],
                            info["src_reference_short"],
                            info["msg"]))
    if info["data"] is not None:
      self.file.write(f"{info["data"]}\n\n")
    self.file.flush()
