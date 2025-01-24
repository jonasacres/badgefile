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
    from .logger import Logger

    if not self.webhook_url:
      return None
    
    if info["severity"] >= Logger.NOTICE:
      line1_prefix = "-# **"
      line1_suffix = "**"
      line2_prefix = "**"
      line2_suffix = "**"
    else:
      line1_prefix = "-# "
      line1_suffix = ""
      line2_prefix = ""
      line2_suffix = ""
    
    msg = "%s[%s] %s@%s %s `%s`%s\n%s%s%s" % (
      line1_prefix,
      info["severity_str_short"],
      info["run_id"],
      self.hostname,
      info["timestamp_str"],
      info["src_reference_short"],
      line1_suffix,
      line2_prefix,
      info["msg"],
      line2_suffix)
    if info["exception"] is not None:
      exc = info["exception"]
      msg += f"\n### __***Exception***__ `{exc.__class__.__name__}`: `{str(exc)}`\n"
      msg += "```" + ''.join(traceback.format_tb(exc.__traceback__)) + "```"

    if info["data"] is not None:
      msg += json.dumps(info["data"], indent=2)

    self.send_discord_message(msg)
  
  def send_discord_message(self, msg):
    try:
      requests.post(self.webhook_url, json={ "content": msg[0:2000] }).raise_for_status()
    except Exception as e:
      # Silently fail - we don't want logging errors to cause more logging
      pass
