import json
from integrations.database import Database
from log.logger import log

class Activity:
  """Describes a single row from the Activity List."""
  
  @classmethod
  def find_attendee(cls, badgefile, row):
    # first go by agaid if present
    # if not, use first, last, mi
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
        if 'name_mi' in row and str(row["name_mi"]).lower() != str(att_info["name_mi"]).lower():
          continue
        candidate = attendee
        break
    
    return candidate
    

  @classmethod
  def with_report_row(cls, badgefile, report_row):
    attendee = cls.find_attendee(badgefile, report_row)
    if attendee is None:
      if report_row['status'].lower() == 'cancelled':
        log.debug(f"Can't find attendee for cancelled row f{report_row}")
      else:
        log.info(f"Can't find attendee for row f{report_row}")
      return None
    return cls(attendee, report_row)

  @classmethod
  def with_db_row(cls, badgefile, db_row):
    return cls.with_report_row(badgefile, db_row)
  
  @classmethod
  def prune_to_activity_registrant_ids(cls, id_list):
    # Ensure id_list contains unique values
    unique_ids = set(id_list)
    log.debug(f"Pruning Activities table to {len(unique_ids)} identifiers")
    
    db = Database.shared()
    
    # Get all existing activity_registrant_ids from the database
    existing_ids_rows = db.query("SELECT DISTINCT activity_registrant_id FROM Activities")
    existing_ids = [row['activity_registrant_id'] for row in existing_ids_rows]
    
    # Find IDs that exist in the database but not in our current list
    ids_to_delete = set(existing_ids) - unique_ids
    
    if ids_to_delete:
        log.debug(f"Deleting {len(ids_to_delete)} activities that are no longer present in CE reports")
        # Convert to list for SQL parameter binding
        ids_list = list(ids_to_delete)
        # Use parameterized query for safety
        placeholders = ','.join(['?' for _ in ids_list])
        db.execute(f"DELETE FROM Activities WHERE activity_registrant_id IN ({placeholders})", ids_list)
    else:
        log.debug("No activities to prune")
  
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
    log.trace(f"syncing activity to db")
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
      log.debug(f"Adding column {name} of type {type}")
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
    
    return [ [key, "INTEGER" if isinstance(info[key], int) else "REAL" if isinstance(info[key], float) else "TEXT"] for key in implicit_keys ]

  def explicit_column_definitions(self):
    return [
    ]
  
  def fee(self):
    return self._info["activity_fee"]
  
  def regtime(self):
    return self._info["regtime"]
  
  def is_meal_plan(self):
    return "meal plan" in self._info["activity_title"].lower()
  
  def num_meal_plans(self):
    if not self.is_meal_plan():
      log.error(f"Attempted to calculate number of meal plans from non-mean-plan activity")
      return None
    
    unit_price = 320
    num_plans = self.fee() / unit_price
    return num_plans
  
  def num_units(self):
    if not self.is_housing():
      log.error(f"Attempted to calculate number of beds from non-housing activity")
      return None
    
    if self.is_dorm_double():
      return self.fee() / 360
    
    if self.is_dorm_single():
      return self.fee() / 680
    
    if self.is_apt1_1room():
      return self.fee() / 760
    
    if self.is_apt1_2room():
      return self.fee() / 1520
    
    if self.is_apt2_1room():
      return self.fee() / 920
    
    if self.is_apt2_2room():
      return self.fee() / 1840
    
    if self.is_apt3():
      return self.fee() / 760
    
    log.error(f"Don't know how to calculate number of units in housing of type '{self._info['activity_title']}'; assuming 1 unit")
    return 1

  def num_beds(self):
    if not self.is_housing():
      log.error(f"Attempted to calculate number of beds from non-housing activity")
      return None
    
    if self.is_apt1_2room() or self.is_apt2_2room():
      return 2*self.num_units()
    else:
      return self.num_units()

  def is_apt1_1room(self):
    return "apartment style 1 with mini-kitchen (1 room of 2)" in self._info["activity_title"].lower()
  
  def is_apt1_2room(self):
    return "apartment style 1 with mini-kitchen (2 rooms)" in self._info["activity_title"].lower()
  
  def is_apt2_1room(self):
    return "apartment style 2 with full kitchen (1 room of 2)" in self._info["activity_title"].lower()
  
  def is_apt2_2room(self):
    return "apartment style 2 with full kitchen (2 rooms)" in self._info["activity_title"].lower()
  
  def is_apt3(self):
    return "apartment style 3 with mini-kitchen (1 room only)" in self._info["activity_title"].lower()
  
  def is_dorm_single(self):
    return "dorm - single occupancy" in self._info["activity_title"].lower()
  
  def is_dorm_double(self):
    return "dorm - double occupancy" in self._info["activity_title"].lower()
  
  def is_housing(self):
    return self.is_apt1_1room() or self.is_apt1_2room() or self.is_apt2_1room() or self.is_apt2_2room() or self.is_apt3() or self.is_dorm_single() or self.is_dorm_double()

  def is_open(self):
    return self._info["status"].lower() in ["open", "paid"]

  def is_banquet(self):
    return "awards banquet" in self._info["activity_title"].lower()
  
  def has_alcohol(self):
    if not self.is_banquet():
      return None
    return "with alcohol" in self._info["activity_title"].lower()

  def is_donation(self):
    return " circle ($" in self._info["activity_title"].lower()
  
  def is_registration_fee(self):
    at = self._info["activity_title"].lower()
    return "registration fee" in at or "registration for youth" in at
  
  def is_full_week_registration(self):
    if not self.is_registration_fee():
      return None
    at = self._info["activity_title"].lower()
    return "full week" in at or "registration for youth" in at
  
  def is_partial_week_registration(self):
    if not self.is_registration_fee():
      return None
    return "partial week" in self._info["activity_title"].lower()

  def roommate_request(self):
    return " | ".join([x for x in [self._info["roommate_a"], self._info["roommate_b"], self._info["roommate_c"]] if x])
  
  def roommate_request_comments(self):
    return " | ".join([x for x in [self._info["roommate_a_comments"], self._info["roommate_b_comments"], self._info["roommate_c_comments"]] if x])
