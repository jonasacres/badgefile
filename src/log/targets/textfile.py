import os
import json
import traceback
from ..log_target import LogTarget

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
    self.file.write("[%s] %s %s %s: %s\n" % (
                            info["severity_str_short"],
                            info['run_id'],
                            info["timestamp_str"],
                            info["src_reference_short"],
                            info["msg"]))
    if info["exception"] is not None:
      exc = info["exception"]
      self.file.write(f"Exception {exc.__class__.__name__}: {str(exc)}")
      self.file.write(''.join(traceback.format_tb(exc.__traceback__)))

    if info["data"] is not None:
      self.file.write(json.dumps(info["data"], indent=2))

    self.file.flush()
