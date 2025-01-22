import hashlib
import os
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

from .database import Database
from .issue_manager import IssueManager
from .id_manager import IdManager
from .clubexpress.reglist import Reglist
from .clubexpress.activity_list import ActivityList
from .clubexpress.activity import Activity
from .util import util


class Attendee:
  def __init__(self, badgefile):
    self.db = Database.shared()
    self._info = {}
    self._badgefile = badgefile
    self._activities = None
    pass

  def badgefile(self):
    return self._badgefile
  
  def latest_reglist(self):
    # need this accessor for our issue checks to access latest raw reglist
    return Reglist.latest()
  
  def latest_activity_list(self):
    # need this accessor for our issue checks to access latest raw reglist
    return ActivityList.latest()

  def load_db_row(self, row):
    self._info.update(row)
    return self
  
  def effective_rank(self):
    # TODO: allow rank override
    return self._info.get('aga_rating', None)

  def load_reglist_row(self, row, sync=True):
    rowinfo = row.info()
    self._info.update(rowinfo)

    agaid = self._info.get("aga_id")
    bfid = self._info.get("badgefile_id")

    if bfid is None:
      if agaid is not None:
        self._info["badgefile_id"] = IdManager.shared().map_aga_id(agaid)
      else:
        self._info["badgefile_id"] = IdManager.shared().map_reg_info(rowinfo)
    elif agaid is not None and agaid != bfid:
      # we have an AGA number and a badgefile ID, but they're not the same!
      # this might be someone who added an AGA number to their registraton later.
      self._info["badgefile_id"] = agaid
      IdManager.shared().set_id_alias(agaid, bfid)
    
    self._info["badge_rating"] = self.badge_rating()
    if self._info["emergency_contact_phone"] is not None:
      self._info["emergency_contact_phone_std"] = util.standardize_phone(self._info["emergency_contact_phone"])

    if sync:
      self.sync_to_db(bfid)
    
    return self
  
  def id(self):
    return self._info["badgefile_id"]
  
  def invalidate_activities(self):
    if "donation_amount" in self._info:
      del self._info["donation_amount"]
    self._activities = None
  
  def populate_derived_fields(self):
    self.donation_amount(True)

  def phone(self):
    phone_keys = ['phone_mobile', 'phone_a', 'phone_cell']
    for key in phone_keys:
      if self._info[key] != None and self._info[key] != "":
        return util.standardize_phone(self._info[key])
    return None

  def party(self, include_cancelled=False):
    party = [x for x in self._badgefile.attendees() if x.primary() == self.primary()]

    if not include_cancelled:
      party = [x for x in party if not x.is_cancelled()]
      if len(party) == 0:
        # This whole reservation is cancelled, so there's no one left in the party.
        return []

    # first element is always the primary registrant
    if not party[0].is_primary():
      non_primaries = [x for x in party if not x.is_primary]
      party = [self.primary()] + non_primaries
    
    return party
  
  def is_cancelled(self):
    return self.info()["status"].lower() == "cancelled"
  
  def is_participant(self):
    return "member" in self._info["regtype"].lower()
  
  def languages(self):
    langstr = str(self._info.get("languages", "")).lower()
    languages = []

    if "korean" in langstr:
      languages.append("korean")
    if "chinese" in langstr:
      languages.append("chinese")
    if "japanese" in langstr:
      languages.append("japanese")
    if "spanish" in langstr:
      languages.append("spanish")
    
    return sorted(languages)
  
  def tournaments(self):
    tournament_str = str(self._info['tournaments']).lower()
    if tournament_str == "none":
      return []
    
    raw_tournaments = tournament_str.split(",")
    tournaments = []

    for rt in raw_tournaments:
      if "die hard" in rt:
        tournaments.append("diehard")
      elif "women" in rt:
        tournaments.append("womens")
      elif "masters" in rt:
        tournaments.append("masters")
      elif "senior" in rt:
        tournaments.append("seniors")
      elif "open" in rt:
        tournaments.append("open")
      else:
        print(f"Unknown tournament option: {rt}")
        tournaments.append(rt)
      
    return sorted(tournaments)
  
  def activities(self):
    if self._activities == None:
      rows = Database.shared().query("SELECT * FROM Activities WHERE badgefile_id=?", [self.id()])
      self._activities = [Activity(self, row) for row in rows]

    return self._activities
  
  def membership_expiration(self):
    if not 'aga_expiration' in self._info or self._info['aga_expiration'] is None:
      return None
    return datetime.strptime(self._info['aga_expiration'], "%m/%d/%Y")

  def badge_rating(self):
    rating = self._info.get("aga_rating", None)
    if rating is None:
      return ""
    rating = float(rating)
    
    from math import floor, ceil

    if rating > 0:
      return str(floor(rating)) + "d"
    else:
      return str(-ceil(rating)) + "k"
  
  def date_of_birth(self):
    if not 'date_of_birth' in self._info or self._info['date_of_birth'] is None:
      return None
    return datetime.strptime(self._info['date_of_birth'], "%m/%d/%Y")
  
  def is_attending_banquet(self):
    for activity in self.activities():
      if activity.is_open() and activity.is_banquet():
        return True
    return False
  
  def has_banquet_alcohol(self):
    for activity in self.activities():
      if activity.is_open() and activity.is_banquet() and activity.has_alcohol():
        return True
    return False
  
  def is_full_week(self):
    for activity in self.activities():
      if activity.is_open() and activity.is_registration_fee() and activity.is_full_week_registration():
        return True
    return False
  
  def is_partial_week(self):
    for activity in self.activities():
      if activity.is_open() and activity.is_registration_fee() and activity.is_partial_week_registration():
        return True
    return False
  
  def donation_amount(self, force=False):
    if force or not 'donation_amount' in self._info or self._info['donation_amount'] == None:
      for activity in self.activities():
        if activity.is_open() and activity.is_donation():
          self._info['donation_amount'] = activity.fee()
          self.sync_to_db()
      self._info['donation_amount'] = 0
      self.sync_to_db()
    return self._info['donation_amount']
  
  def merge_activity_info(self):
    self.donation_amount(True) # force population of donation_amount
  
  def merge_tdlist_info(self, tdlist_info):
    for key, value in tdlist_info.items():
      self._info[key] = value
    self.sync_to_db()
  
  def sync_to_db(self, existing_id=None):
    if existing_id is None:
      existing_id = self.id()

    self.ensure_attendee_table()
    info = self.info()
    if 'json' in info:
      del(info['json'])

    keys = [defn[0] for defn in self.column_definitions()]
    set_clause = "badgefile_id=?, json=?, " + ", ".join([f"{key}=?" for key in keys])
    base_args = [self.id(), json.dumps(info)] + [info[key] for key in keys]
    update_args = base_args + [existing_id]

    update_sql = f"UPDATE Attendees SET {set_clause} WHERE badgefile_id=?"
    affected_rows = self.db.execute(update_sql, update_args)

    if affected_rows == 0:
      insert_sql = f"INSERT INTO Attendees (badgefile_id, json, {','.join(keys)}) VALUES (?, ?, {', '.join(['?' for _ in keys])})"
      self.db.execute(insert_sql, base_args)

    if existing_id != self.id():
      # TODO: placeholder. we're going to want a column for the primary registrant's badgefile id.
      # if we changed someone's bfid, we need to make sure everyone who listed them as a primary registrant is updated to match.
      pass
  
  def ensure_attendee_table(self):
    self.db.execute("CREATE TABLE IF NOT EXISTS Attendees(badgefile_id INTEGER NOT NULL PRIMARY KEY, json TEXT NOT NULL)")
    defns_dict = { col[0]: col[1] for col in self.column_definitions() } 
    existing_cols = self.db.columns_of_table("Attendees")
    expected_cols = defns_dict.keys()
    missing_columns = list(set(expected_cols) - set(existing_cols))
    missing_defns = [[col, defns_dict[col]] for col in missing_columns if col in defns_dict]
    
    for defn in missing_defns:
      name, type = defn
      query = f"ALTER TABLE Attendees ADD COLUMN {name} {type} DEFAULT NULL;"
      self.db.execute(query)

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
  
  # return the attendee's current info, based on latest regdata with overrides applied
  def info(self):
    return self._info

  def refresh(self, row=None):
    if row == None:
      row = self.latest_row()
    self.load_reglist_row(row)
  
  # returns the sha256 of the current data
  def datahash(self):
    # Sort the dictionary by keys alphabetically
    sorted_items = sorted(self.info().items())

    # Create the concatenated string in the format "key1|value1|key2|value2|..."
    concatenated_string = "|".join(f"{key}|{value}" for key, value in sorted_items)

    # Calculate the SHA256 hash of the resulting string
    sha256_hash = hashlib.sha256(concatenated_string.encode('utf-8')).hexdigest()

    return sha256_hash

  # calculate the heuristic similarity between this attendee and the attendee described
  # in a registrant data row    
  def similarity_score(self, row):
    score = 0
    aa = self.info()

    # The more I look at this the more I hate it.
    # TODO: refine this based on real data
    tests = [
      # all of these are basically conclusive, though AGA number is the gold standard
      [99999, ["aga_id"]],
      [10000, ["name_given", "name_family", "date_of_birth"]],
      [9000, ["name_given", "name_family", "name_mi"]],
      [9000, ["name_given", "name_family", "phone_cell"]], # TODO: standardize phone numbers (both format AND source field)
      [9000, ["name_given", "name_family", "addr1", "postcode"]],

      # TODO: these don't really make sense...

      [50, ["name_family", "date_of_birth"]],
      [30, ["addr1", "postcode"]],
      [30, ["phone_cell"]],
    ]

    # TODO: allow flip-flopping of given/family names

    for test in tests:
      passed = True
      for key in test[1]:
        if key not in row or key not in aa or row[key] is None:
          passed = False
          break
        if str(row[key]).lower() != str(aa[key]).lower():
          passed = False
          break

      score += test[0] if passed else 0
          
    return score
  
  # return a dict of previously identified issues that are not marked as resolved in the database
  def open_issues(self):
    return IssueManager.shared().open_issues_for_attendee(self)

  # return a list of previously identified issues regardless of status
  def all_issues(self):
    return IssueManager.shared().all_issues_for_attendee(self)

  # scan for new issues and insert them into the database if no similar issue is open for this user;
  # mark previous issues as resolved if the issue has been corrected.
  def scan_issues(self):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    issue_dir = os.path.join(script_dir, "issue_checks")
    current_issues = {}

    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(project_root))


    if not self.is_cancelled():
      # Run all the issue check scripts, but only for non-cancelled attendees
      # (thus cancelled attendees have no outstanding issues)
      for filename in os.listdir(issue_dir):
        if "__" in filename:
          continue
        if filename.endswith(".py"):
          file_path = os.path.join(issue_dir, filename)
        
        # Dynamically import the script
        issue_type = filename[:-3]  # Strip .py extension
        spec = importlib.util.spec_from_file_location(issue_type, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check for a function named 'run_check' and execute it
        if hasattr(module, "run_check"):
          issue_data = module.run_check(self)
          if issue_data is not None:  # Only collect non-None results
            current_issues[issue_type] = issue_data

    existing_issues = self.open_issues()
    new_issues = list(current_issues.keys() - existing_issues.keys())
    resolved_issues = list(existing_issues.keys() - current_issues.keys())
    continued_issues = list(existing_issues.keys() & current_issues.keys())

    for issue_type in new_issues:
      IssueManager.shared().create(self, issue_type, current_issues[issue_type])

    for issue_type in resolved_issues:
      IssueManager.shared().resolve(self, issue_type)

    for issue_type in continued_issues:
      if existing_issues[issue_type] != current_issues[issue_type]:
        IssueManager.shared().update(self, issue_type, current_issues[issue_type])

    return current_issues      
  
  # returns a list of reglist rows referring to this user
  def reglist_rows(self):
    return [x for x in Reglist.latest().rows() if x.attendee().id() == self.id()]
  
  # returns the latest ReglistRow for this user
  def latest_row(self):
    return self.reglist_rows()[-1]
  
  # boolean: is this the primary registrant?
  def is_primary(self):
    return self.info()["is_primary"].lower() == "true"
  
  # return self if is_primary, otherwise returns reference to primary registrant
  def primary(self):
    if self.is_primary():
      return self
    
    primary_registrant_id = self._info.get("primary_registrant_id")
    if primary_registrant_id:
      return self.badgefile().lookup_attendee(primary_registrant_id)
    
    return None
  
  def set_primary_registrant(self, primary_bfid):
    if primary_bfid != self._info.get("primary_registrant_id"):
      self._info["primary_registrant_id"] = primary_bfid
      self.sync_to_db()
