from integrations.database import Database
from datetime import datetime
from log.logger import log
from model.notification_manager import NotificationManager

class AttendeeNotEligible(Exception):
    """Exception raised when an attendee tries to scan in but is not eligible."""
    pass

class Event:
  _instances = {}

  @classmethod
  def exists(cls, name):
    db = Database.shared()
    status_table = f"event_{name}_status"
    result = db.query(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", [status_table])
    return len(result) > 0

  def __init__(self, name):
    self.name = name
    self.ensure_db()
  
  def mark_attendee_eligible(self, attendee, is_eligible=True):
    # insert a row into the table for the attendee (if one does not exist for badgefile_id=attendee.id()) with scan_count=0
    # no-op if a row already exists for that attendee with the same eligibility status
    db = Database.shared()
    
    # Check if attendee already exists in status table
    status_table = f"event_{self.name}_status"
    result = db.query(f"SELECT * FROM {status_table} WHERE badgefile_id = ?", [attendee.id()])
    
    # Check if we need to make any changes
    if result and result[0]['is_eligible'] == is_eligible:
      # Status already matches, no need to update anything
      return
    
    # Record this eligibility change in the enrollments table first
    enrollments_table = f"event_{self.name}_enrollments"
    db.execute(f"INSERT INTO {enrollments_table} (badgefile_id, timestamp_changed, is_eligible) VALUES (?, ?, ?)",
              [attendee.id(), datetime.now().timestamp(), is_eligible])
    
    # Then update or insert into status table
    if not result:
      # Insert new row with scan_count=0 and specified is_eligible value
      db.execute(f"INSERT INTO {status_table} (badgefile_id, scan_count, is_eligible) VALUES (?, 0, ?)", 
                [attendee.id(), is_eligible])
    else:
      # Update existing row with new eligibility status
      db.execute(f"UPDATE {status_table} SET is_eligible = ? WHERE badgefile_id = ?",
                [is_eligible, attendee.id()])
    
    NotificationManager.shared().notify("event", {"event": self, "attendee": attendee, "action": "enrollment", "data": {"is_eligible": is_eligible}})
  
  def scan_in_attendee(self, attendee, is_reset=False):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    scans_table = f"event_{self.name}_scans"
    
    # Check if attendee exists in status table
    result = db.query(f"SELECT * FROM {status_table} WHERE badgefile_id = ?", [attendee.id()])
    if not self.is_attendee_eligible(attendee):
      raise AttendeeNotEligible(f"Attendee with ID {attendee.id()} is not eligible for event {self.name}")
    
    # Record scan
    current_time = datetime.now().timestamp()
    db.execute(f"INSERT INTO {scans_table} (badgefile_id, timestamp_scanned, is_reset) VALUES (?, ?, ?)",
              [attendee.id(), current_time, is_reset])
    
    if is_reset:
      db.execute(f"UPDATE {status_table} SET scan_count = 0 WHERE badgefile_id = ?", [attendee.id()])
    else:
      # Increment scan_count
      db.execute(f"UPDATE {status_table} SET scan_count = scan_count + 1 WHERE badgefile_id = ?",
                [attendee.id()])
    
    # Get and return the new scan count
    updated_result = db.query(f"SELECT scan_count FROM {status_table} WHERE badgefile_id = ?", [attendee.id()])
    scan_count = updated_result[0]['scan_count']

    log.debug(f"Scanned attendee {attendee.full_name()} into {self.name}, is_reset={is_reset}; new count {scan_count}")
    NotificationManager.shared().notify("event", {"event": self, "attendee": attendee, "action": "scan", "data": {"is_reset": is_reset, "num_times_attendee_scanned": scan_count}})
    return scan_count

  def is_attendee_eligible(self, attendee):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    
    result = db.query(f"SELECT is_eligible FROM {status_table} WHERE badgefile_id = ?", [attendee.id()])
    if result and result[0]['is_eligible']:
      return True
    return False

  def num_times_attendee_scanned(self, attendee):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    
    result = db.query(f"SELECT scan_count FROM {status_table} WHERE badgefile_id = ?", [attendee.id()])
    if result:
      return result[0]['scan_count']
    return 0
  
  def scan_counts(self):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    
    result = db.query(f"SELECT badgefile_id, scan_count, is_eligible FROM {status_table}")
    
    status_dict = {}
    for row in result:
      status_dict[row['badgefile_id']] = {
        'scan_count': row['scan_count'],
        'is_eligible': row['is_eligible']
      }
    
    return status_dict

  def num_scanned_attendees(self, include_ineligible=True):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    
    if include_ineligible:
      result = db.query(f"SELECT COUNT(*) as count FROM {status_table} WHERE scan_count > 0")
    else:
      result = db.query(f"SELECT COUNT(*) as count FROM {status_table} WHERE scan_count > 0 AND is_eligible = TRUE")
    
    return result[0]['count']

  def num_eligible_attendees(self, include_all_scanned=True):
    db = Database.shared()
    status_table = f"event_{self.name}_status"
    
    if include_all_scanned:
      result = db.query(f"SELECT COUNT(*) as count FROM {status_table} WHERE is_eligible = TRUE OR scan_count > 0")
    else:
      result = db.query(f"SELECT COUNT(*) as count FROM {status_table} WHERE is_eligible = TRUE")
    
    return result[0]['count']

  def ensure_db(self):
    db = Database.shared()
    
    # Create status table
    status_table = f"event_{self.name}_status"
    db.execute(f"""
      CREATE TABLE IF NOT EXISTS {status_table} (
        badgefile_id INTEGER PRIMARY KEY,
        scan_count INTEGER NOT NULL DEFAULT 0,
        is_eligible BOOLEAN NOT NULL DEFAULT FALSE
      )
    """)
    
    # Create scans table
    scans_table = f"event_{self.name}_scans"
    db.execute(f"""
      CREATE TABLE IF NOT EXISTS {scans_table} (
        scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        badgefile_id INTEGER NOT NULL,
        timestamp_scanned REAL NOT NULL,
        is_reset BOOLEAN NOT NULL DEFAULT FALSE
      )
    """)
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_{scans_table}_timestamp ON {scans_table} (timestamp_scanned)")
    
    # Create enrollments table
    enrollments_table = f"event_{self.name}_enrollments"
    db.execute(f"""
      CREATE TABLE IF NOT EXISTS {enrollments_table} (
        enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        badgefile_id INTEGER NOT NULL,
        timestamp_changed REAL NOT NULL,
        is_eligible BOOLEAN NOT NULL
      )
    """)
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_{enrollments_table}_timestamp ON {enrollments_table} (badgefile_id, timestamp_changed)")

  def consistency_check(self):
    self.consistency_check_enrollments()
    self.consistency_check_scans()

  def consistency_check_enrollments(self):
    # for each unique badgegile_id from enrollments:
    #   select most recent row from enrollments for that id
    #   update row in status to ensure is_eligible is consistent with value from most recent enrollments row
    #   create row in status if no such row exists, with scan_count=0
    db = Database.shared()
    enrollments_table = f"event_{self.name}_enrollments"
    status_table = f"event_{self.name}_status"
    
    # Get unique badgefile_ids from enrollments
    unique_ids = db.query(f"SELECT DISTINCT badgefile_id FROM {enrollments_table}")
    
    for id_row in unique_ids:
      badgefile_id = id_row['badgefile_id']
      
      # Get most recent enrollment record for this badgefile_id
      latest_enrollment = db.query(f"""
        SELECT is_eligible FROM {enrollments_table} 
        WHERE badgefile_id = ? 
        ORDER BY timestamp_changed DESC 
        LIMIT 1
      """, [badgefile_id])
      
      if latest_enrollment:
        is_eligible = latest_enrollment[0]['is_eligible']
        
        # Check if attendee exists in status table
        status_row = db.query(f"SELECT * FROM {status_table} WHERE badgefile_id = ?", [badgefile_id])
        
        if status_row:
          # Update existing row
          db.execute(f"UPDATE {status_table} SET is_eligible = ? WHERE badgefile_id = ?", 
                    [is_eligible, badgefile_id])
        else:
          # Create new row
          db.execute(f"INSERT INTO {status_table} (badgefile_id, scan_count, is_eligible) VALUES (?, 0, ?)",
                    [badgefile_id, is_eligible])

  def consistency_check_scans(self):
    from log.logger import log
    
    db = Database.shared()
    scans_table = f"event_{self.name}_scans"
    status_table = f"event_{self.name}_status"
    
    # Get unique badgefile_ids from scans
    unique_ids = db.query(f"SELECT DISTINCT badgefile_id FROM {scans_table}")
    
    for id_row in unique_ids:
      badgefile_id = id_row['badgefile_id']
      
      # Get all scans for this badgefile_id ordered by timestamp
      scans = db.query(f"""
        SELECT is_reset FROM {scans_table} 
        WHERE badgefile_id = ? 
        ORDER BY timestamp_scanned ASC
      """, [badgefile_id])
      
      # Calculate correct scan count
      counter = 0
      for scan in scans:
        if not scan['is_reset']:
          counter += 1
        else:
          counter = 0
      
      # Ensure status table is consistent
      status_row = db.query(f"SELECT * FROM {status_table} WHERE badgefile_id = ?", [badgefile_id])
      
      if status_row:
        db.execute(f"UPDATE {status_table} SET scan_count = ? WHERE badgefile_id = ?", 
                  [counter, badgefile_id])
      else:
        log.warn(f"No status row found for badgefile_id {badgefile_id} in event {self.name}, but has scan count of {counter} after {len(scans)} scan rows")
