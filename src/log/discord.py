import json
import traceback
import requests
import socket
from .log_target import LogTarget

class Discord(LogTarget):
  def __init__(self, webhook_url):
    super().__init__()
    self.webhook_url = webhook_url
    self.hostname = socket.gethostname()
    pass

  def log_msg(self, info):
    msg = "[%s] %s@%s %s %s\n%s" % (
      info["severity_str_short"],
      info["run_id"],
      self.hostname,
      info["timestamp_str"],
      info["src_reference_short"],
      info["msg"])
    if info["exception"] is not None:
      exc = info["exception"]
      msg += f"\nException {exc.__class__.__name__}: {str(exc)}\n"
      msg += ''.join(traceback.format_tb(exc.__traceback__))

    if info["data"] is not None:
      msg += json.dumps(info["data"], indent=2)

    self.send_discord_message(msg)
  
  def send_discord_message(self, msg):
    try:
      requests.post(self.webhook_url, json={ "content": msg[0:2000] }).raise_for_status()
    except Exception as e:
      # Silently fail - we don't want logging errors to cause more logging
      pass
