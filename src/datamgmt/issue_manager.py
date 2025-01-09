import json

from .database import Database

class IssueManager:
  _shared = None
  
  @classmethod
  def shared(cls):
    if cls._shared is None:
      cls._shared = cls()
    return cls._shared

  def __init__(self):
    self.create_table()

  def create_table(self):
    # Create the table
    Database.shared().execute("""
        CREATE TABLE IF NOT EXISTS Issues (
            issue_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            badgefile_id INTEGER NOT NULL,
            issue_type TEXT NOT NULL,
            issue_data TEXT,
            status INTEGER NOT NULL DEFAULT 0,
            time_first_observed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            time_resolved TIMESTAMP
        )
    """)

    # Add an index on (badgefile_id, issue_type)
    Database.shared().execute("""
        CREATE INDEX IF NOT EXISTS idx_badgefile_id_issue_type ON Issues (badgefile_id, issue_type)
    """)

  def open_issues_for_attendee(self, attendee):
    results = Database.shared().query("SELECT issue_type, issue_data FROM Issues WHERE badgefile_id=? AND status=0", [attendee.id()])
    return {row["issue_type"]: row["issue_data"] for row in results}

  def all_issues_for_attendee(self, attendee):
    results = Database.shared().query("SELECT issue_type, issue_data FROM Issues WHERE badgefile_id=?", [attendee.id()])
    return {row["issue_type"]: row["issue_data"] for row in results}

  def create(self, attendee, issue_type, issue_data):
    issue_data_json = json.dumps(issue_data)
    Database.shared().execute("INSERT INTO Issues (badgefile_id, issue_type, issue_data) VALUES (?, ?, ?)",
                            [attendee.id(), issue_type, issue_data_json])
    pass

  def update(self, attendee, issue_type, issue_data):
    issue_data_json = json.dumps(issue_data)
    Database.shared().execute("UPDATE Issues SET issue_data=? WHERE badgefile_id=? AND issue_type=?",
                            [issue_data_json, attendee.id(), issue_type])

  def resolve(self, attendee, issue_type):
    Database.shared().execute("UPDATE Issues SET status=1, time_resolved=CURRENT_TIMESTAMP WHERE badgefile_id=? AND issue_type=?",
                            [attendee.id(), issue_type])



