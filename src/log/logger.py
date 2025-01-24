import inspect
import os
import random
from datetime import datetime

from .targets.textfile import Textfile
from .targets.console import Console
from .targets.discord import Discord

class Logger:
  TRACE    = 0
  DEBUG    = 1
  INFO     = 2
  NOTICE   = 3
  WARN     = 4
  ERROR    = 5
  CRITICAL = 6
  FATAL    = 7

  SEVERITY_NAMES = {
    TRACE:    "TRACE",
    DEBUG:    "DEBUG", 
    INFO:     "INFO",
    NOTICE:   "NOTICE",
    WARN:     "WARN",
    ERROR:    "ERROR",
    CRITICAL: "CRITICAL",
    FATAL:    "FATAL",
  }

  _default = None

  @classmethod
  def default(cls):
    if cls._default == None:
      cls._default = cls()
    
    return cls._default

  def __init__(self):
    self.targets = []
    pass

  def add_target(self, target):
    self.targets.append(target)

  def caller(self):
    # Get the current stack frame and walk up until we find a non-Logger caller
    frame = inspect.currentframe()
    try:
      while frame:
        # Move up one frame
        frame = frame.f_back
        if not frame:
          break
          
        # Get code info for this frame
        code = frame.f_code
        
        # Skip if this is any function defined in this file
        if code.co_filename == __file__:
          continue
          
        # Found our caller - format the response
        filename = os.path.basename(code.co_filename)
        return f"{filename}:{frame.f_lineno}"
        
      return "unknown:0"
      
    finally:
      del frame  # Avoid reference cycles

  def logmsg(self, msg, severity=DEBUG, data=None, exception=None):
    timestamp = datetime.now()
    src_reference = self.caller()

    for target in self.targets:
      target.log(timestamp, run_id, src_reference, severity, msg, data, exception)

  def trace(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.TRACE, data, exception)

  def debug(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.DEBUG, data, exception)

  def info(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.INFO, data, exception)

  def notice(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.NOTICE, data, exception)
  
  def warn(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.WARN, data, exception)

  def error(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.ERROR, data, exception)

  def critical(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.CRITICAL, data, exception)

  def fatal(self, msg, data=None, exception=None):
    return self.logmsg(msg, self.FATAL, data, exception)

def setup_default_logger():
  default = Logger.default()
  if not hasattr(default, '_Logger__setup'):

    default.add_target(Console())
    default.add_target(Textfile("badgefile.log"))

    from util.secrets import secret
    discord_target = Discord(secret("discord_log_webhook", None))
    discord_target.set_severity(Logger.WARN)
    default.add_target(discord_target)

    default._Logger__setup = True

log = Logger.default()
run_id = f"{random.randint(0, 0xFFFFFFFF):08x}"
setup_default_logger()
