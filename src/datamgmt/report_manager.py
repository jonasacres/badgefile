from .database import Database

class ReportManager:
  _shared = None

  @classmethod
  def shared(cls):
    if cls._shared == None:
      cls._shared = cls()
    return cls._shared

  def __init__(self):
    self.db = Database.shared()
    self.create_tables()
    pass

  def create_tables(self):
    self.create_report_pulls_table()
  
  def create_report_pulls_table(self):
    self.db.execute("CREATE TABLE IF NOT EXISTS ReportPulls (pull_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, report_name TEXT, hash TEXT, path TEXT, pulled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
  
  def download_all(self):
    # TODO: DEPRECATED DUE TO DEPENDENCY CYCLE
    # reglist = Reglist.download()
    # TODO: tdlist
    # TODO: registrant fees and payments
    # TODO: housing
    # TODO: excursions?

    return { "reglist": reglist }
  
  def pulled_report(self, name, hash, path):
    self.db.execute("INSERT INTO ReportPulls (report_name, hash, path) VALUES (?, ?, ?)", [name, hash, path])
  
  def last_report_info(self, name):
    results = self.db.query("SELECT * FROM ReportPulls WHERE report_name=? ORDER BY pulled_at DESC LIMIT 1", [name])
    return results[0] if len(results) > 0 else None
