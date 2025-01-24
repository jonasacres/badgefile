import os

class LogTarget:
  """Base class for log targets. Don't instantiate directly."""

  def __init__(self):
    from .logger import Logger
    self._data_severity = Logger.INFO
    self._severity = Logger.DEBUG
  
  def set_severity(self, severity):
    self._severity = severity
    return self
  
  def set_data_severity(self, severity):
    self._data_severity = severity
    return self
  
  def log(self, timestamp, run_id, src_reference, severity, msg, data, exception):
    from .logger import Logger
    info = {
      "timestamp":           timestamp,
      "timestamp_str":       timestamp.strftime("%Y-%m-%d %H:%M:%S"),
      "run_id":              run_id,
      "severity":            severity,
      "severity_str":        Logger.SEVERITY_NAMES.get(severity, "UNKNOWN"),
      "severity_str_short":  str(severity),
      "src_reference":       src_reference, 
      "src_reference_short": os.path.basename(src_reference),
      "data":                data if severity >= self._data_severity else None,
      "exception":           exception,
      "msg":                 msg,
    }

    if severity >= self._severity:
      self.log_msg(info)

