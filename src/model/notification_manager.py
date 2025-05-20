class NotificationManager:
  _instance = None

  @classmethod
  def shared(cls):
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance
  
  def __init__(self):
    self.observers = []
  
  def notify(self, key, notification):
    for observer in self.observers:
      observer['callback'](key, notification)
  
  def observe(self, callback):
    self.observers.append({'callback': callback})
  