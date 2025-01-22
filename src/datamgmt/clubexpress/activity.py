import json
from ..database import Database
from log.logger import *

class Activity:
  @classmethod
  def find_attendee(cls, badgefile, row):
    # first go by agaid if persent
    # if not, use first, last, mi and trans ref num
    candidate = None
    if "badgefile_id" in row:
      candidate = badgefile.lookup_attendee(row["badgefile_id"])
    if candidate is None and "aga_id" in row:
      badgefile.lookup_attendee(row["aga_id"])
    if candidate is None:
      for attendee in badgefile.attendees():
        att_info = attendee.info()
        if str(row["name_family"]).lower() != str(att_info["name_family"]).lower():
          continue
        if str(row["name_given"]).lower() != str(att_info["name_given"]).lower():
          continue
        if str(row["name_mi"]).lower() != str(att_info["name_mi"]).lower():
          continue
        candidate = attendee
        break
    
    return candidate
    

  @classmethod
  def with_report_row(cls, badgefile, report_row):
    # TODO: find an attendee in the badgefile matching the supplied report row
    attendee = cls.find_attendee(badgefile, report_row)
    if attendee is None:
      # TODO: scary log message; we can't find a matching attendee!
      log_critical(f"Can't find attendee for row f{report_row}")
      return None
    return cls(attendee, report_row)

  @classmethod
  def with_db_row(cls, badgefile, db_row):
    return cls.with_report_row(badgefile, db_row)

  def __init__(self, attendee, row):
    self.db = Database.shared()
    self.attendee = attendee
    self._info = {}
    self.parse_report_row(row)

  def info(self):
    return self._info

  def parse_report_row(self, row):
    self._info.update(row)
    self.sync_to_db()
    return self

  def sync_to_db(self):
    self.ensure_activities_table()
    info = self.info()
    if 'json' in info:
      del(info['json'])

    keys = [defn[0] for defn in self.column_definitions()]
    set_clause = "badgefile_id=?, json=?, " + ", ".join([f"{key}=?" for key in keys])
    base_args = [self.attendee.id(), json.dumps(info)] + [info[key] for key in keys]
    update_args = base_args + [info["activity_registrant_id"]]

    update_sql = f"UPDATE Activities SET {set_clause} WHERE activity_registrant_id=?"
    affected_rows = self.db.execute(update_sql, update_args)

    if affected_rows == 0:
      insert_sql = f"INSERT INTO Activities (badgefile_id, json, {','.join(keys)}) VALUES (?, ?, {', '.join(['?' for _ in keys])})"
      self.db.execute(insert_sql, base_args)
    
  def ensure_activities_table(self):
    self.db.execute("CREATE TABLE IF NOT EXISTS Activities(badgefile_id INTEGER NOT NULL, json TEXT NOT NULL)")
    defns_dict = { col[0]: col[1] for col in self.column_definitions() } 
    existing_cols = self.db.columns_of_table("Activities")
    expected_cols = defns_dict.keys()
    missing_columns = list(set(expected_cols) - set(existing_cols))
    missing_defns = [[col, defns_dict[col]] for col in missing_columns if col in defns_dict]
    
    for defn in missing_defns:
      name, type = defn
      query = f"ALTER TABLE Activities ADD COLUMN {name} {type} DEFAULT NULL;"
      self.db.execute(query)
    
    # TODO: add indexes on [badgefile_id] and [activity_registrant_id]

  def column_definitions(self):
    return self.implicit_column_definitions() + self.explicit_column_definitions()

  def implicit_column_definitions(self):
    info = self.info()
    implicit_keys = info.keys() - self.explicit_column_definitions()
    if "badgefile_id" in implicit_keys:
      implicit_keys.remove("badgefile_id") # we manually handle this column outside of implicit_column_definitions and explicit_column_definitions
    if "json" in implicit_keys:
      implicit_keys.remove("json") # ditto
    return [ [key, "INTEGER" if isinstance(info[key], int) else "TEXT"] for key in implicit_keys ]

  def explicit_column_definitions(self):
    return [
    ]
  

  def fee(self):
    return self._info["activity_fee"]

  def is_open(self):
    return self._info["status"].lower() == "open"

  def is_banquet(self):
    return "awards banquet" in self._info["activity_title"].lower()
  
  def has_alcohol(self):
    if not self.is_banquet():
      return None
    return "with alcohol" in self._info["activity_title"].lower()

  def is_donation(self):
    return "friends of the congress" in self._info["activity_title"].lower()
  
  def is_registration_fee(self):
    return "registration fee" in self._info["activity_title"].lower()
  
  def is_full_week_registration(self):
    if not self.is_registration_fee():
      return None
    return "full week" in self._info["activity_title"].lower()
  
  def is_partial_week_registration(self):
    if not self.is_registration_fee():
      return None
    return "partial week" in self._info["activity_title"].lower()
