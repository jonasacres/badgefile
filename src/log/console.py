import json
import traceback
from .log_target import LogTarget

class Console(LogTarget):
  def log_msg(self, info):
    print("[%s] %s %30s -- %s" % (
           info["severity_str_short"],
           info["timestamp_str"],
           info["src_reference_short"],
           info["msg"]))
    
    if info["exception"] is not None:
      exc = info["exception"]
      print(f"Exception {exc.__class__.__name__}: {str(exc)}")
      print(''.join(traceback.format_tb(exc.__traceback__)))

    if info["data"] is not None:
      print(json.dumps(info["data"], indent=2))
      
