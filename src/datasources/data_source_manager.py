from integrations.database import Database

class DataSourceManager:
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
    self.create_data_source_pulls_table()
  
  def create_data_source_pulls_table(self):
    self.db.execute("CREATE TABLE IF NOT EXISTS DataSourcePulls (pull_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, data_source TEXT, hash TEXT, path TEXT, pulled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
  
  def pulled_datasource(self, name, hash, path):
    self.db.execute("INSERT INTO DataSourcePulls (data_source, hash, path) VALUES (?, ?, ?)", [name, hash, path])
  
  def last_datasource_info(self, name):
    results = self.db.query("SELECT * FROM DataSourcePulls WHERE data_source=? ORDER BY pulled_at DESC LIMIT 1", [name])
    return results[0] if len(results) > 0 else None
