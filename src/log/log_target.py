import os

class LogTarget:
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
  
  def log(self, timestamp, src_reference, severity, msg, data, exception):
    from .logger import Logger
    info = {
      "timestamp":           timestamp,
      "timestamp_str":       timestamp.strftime("%Y-%m-%d %H:%M:%S"),
      "severity":            severity,
      "severity_str":        Logger.SEVERITY_NAMES.get(severity, "UNKNOWN"),
      "severity_str_short":  Logger.SEVERITY_NAMES.get(severity, str(severity))[0],
      "src_reference":       src_reference, 
      "src_reference_short": os.path.basename(src_reference),
      "data":                data if severity >= self._data_severity else None,
      "exception":           exception,
      "msg":                 msg,
    }

    if severity >= self._severity:
      self.log_msg(info)

