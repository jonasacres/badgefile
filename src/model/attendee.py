import hashlib
import os
import importlib.util
import json
import sys
import hmac
from datetime import datetime
from pathlib import Path

from integrations.database import Database
from .issue_manager import IssueManager
from .id_manager import IdManager
from datasources.clubexpress.reglist import Reglist
from datasources.clubexpress.activity_list import ActivityList
from datasources.clubexpress.activity import Activity
from util.util import standardize_phone
from util.secrets import secret

from log.logger import log


class Attendee:
  """Describes a single attendee at the Congress. Combines data from multiple datasources to present a cohesive view of each attendee."""

  def __init__(self, badgefile):
    self._info = {}
    self._badgefile = badgefile
    self._activities = None
    pass

  def badgefile(self):
    return self._badgefile
  
  def badge(self):
    from artifacts.pdfs.badge import Badge
    return Badge(self)
  
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
    if self._info.get('override_rating', None):
      return self._info['override_rating']
    return self._info.get('aga_rating', None)
  
  def aga_rating(self):
    return self._info.get('aga_rating', None)

  def load_reglist_row(self, rowinfo, sync=True):
    if hasattr(rowinfo, 'info') and callable(getattr(rowinfo, 'info')):
      rowinfo = rowinfo.info()
    else:
      rowinfo = rowinfo
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
      self._info["emergency_contact_phone_std"] = standardize_phone(self._info["emergency_contact_phone"])

    if sync:
      self.sync_to_db(bfid)
    
    return self
  
  def id(self):
    return self._info["badgefile_id"]
  
  def datamatrix_content(self):
    return ("25GC" + str(self.id())).encode('utf8')
  
  def hash_id(self):
    if "hash_id" in self._info and self._info["hash_id"] is not None:
      return self._info["hash_id"]
    
    # Create a SHA256 HMAC of the attendee ID using the salt from secrets
    key = secret('hash_id_salt').encode('utf-8')
    message = str(self.id()).encode('utf-8')
    h = hmac.new(key, message, hashlib.sha256)
    
    # Store the hexdigest as the hash_id
    self._info["hash_id"] = h.hexdigest()[0:12]
    self.sync_to_db()
    
    return self._info["hash_id"]
  
  def invalidate_activities(self):
    if "donation_amount" in self._info:
      del self._info["donation_amount"]
    self._activities = None
  
  def populate_derived_fields(self):
    self.recalculate_donation_info()

  def title(self):
    info = self.info()
    if "title" in info and info["title"] != "":
      return info["title"]
    
    if self.is_participant:
      return "Player"
    else:
      return "Non-participant"

  def phone(self):
    phone_keys = ['phone_mobile', 'phone_a', 'phone_cell']
    for key in phone_keys:
      if self._info[key] != None and self._info[key] != "":
        return standardize_phone(self._info[key])
    return None

  def regtime(self):
    return datetime.strptime(self._info['regtime'], "%m/%d/%Y %I:%M:%S %p")

  def party(self, include_cancelled=False):
    party = self._badgefile.parties()[self.primary()]

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
        log.warn(f"Unknown tournament option: {rt}")
        tournaments.append(rt)
      
    return sorted(tournaments)
  
  def activities(self):
    if self._activities == None:
      rows = Database.shared().query("SELECT * FROM Activities WHERE badgefile_id=?", [self.id()])
      self._activities = [Activity(self, row) for row in rows]

    return self._activities
  
  def membership_expiration(self):
    if not 'aga_expiration_date' in self._info or self._info['aga_expiration_date'] is None:
      return None
    return datetime.strptime(self._info['aga_expiration_date'], "%m/%d/%Y")
  
  def meal_status(self):
    party_size = len(self.party())
    pmp = self.party_meal_plan()
    meal_plans = pmp.num_meal_plans() if pmp else 0

    if meal_plans >= party_size:
      return "yes"
    elif meal_plans == 0:
      return "no"
    else:
      return "ambiguous"

  def badge_rating(self):
    rating = self.effective_rank()
    if rating is None:
      return ""
    rating = float(rating)
    
    from math import floor, ceil

    if rating > 0:
      return str(floor(rating)) + "d"
    else:
      return str(-ceil(rating)) + "k"
  
  def rating_override_requested(self):
    return self._info["rank_playing"].lower() not in ["use aga rank", "not playing in any tournaments"]
  
  def date_of_birth(self):
    if not 'date_of_birth' in self._info or self._info['date_of_birth'] is None:
      return None
    return datetime.strptime(self._info['date_of_birth'], "%m/%d/%Y")

  def age_at_congress(self):
    congress_date = datetime(2025, 7, 13)
    birth_date = self.date_of_birth()
    return congress_date.year - birth_date.year - ((congress_date.month, congress_date.day) < (birth_date.month, birth_date.day))
  
  def full_name(self):
    if self._info['name_mi'] is not None:
      return f"{self._info['name_family']}, {self._info['name_given']} {self._info['name_mi']}"
    else:
      return f"{self._info['name_family']}, {self._info['name_given']}"
  
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
  
  def recalculate_donation_info(self):
    donations = [act for act in self.activities() if act.is_open() and act.is_donation()]
    self._info['donation_amount'] = 0
    names = []

    if len(donations) > 0:
      for donation in donations:
        if donation.is_open():
          name_fields = ['foc_name_platinum', 'foc_name_gold', 'foc_name_silver']
          self._info['donation_amount'] += donation.fee()
          selected_names = [donation.info()[name] for name in name_fields if donation.info()[name] != None]
          names += selected_names
    
    if self._info['donation_amount'] >= 250.0:
      self._info['donation_tier'] = 'platinum'
    elif self._info['donation_amount'] >= 50.0:
      self._info['donation_tier'] = 'gold'
    elif self._info['donation_amount'] > 0.0:
      self._info['donation_tier'] = 'silver'
    else:
      self._info['donation_tier'] = 'nondonor'

    # TODO: figure out how to get these from the activity sheet
    is_anon = False
    for name in names:
      is_anon |= name.lower() in ['anon', 'anonymous']

    self._info['donation_name'] = names[0] if len(names) > 0 else f"{self._info['name_given']} {self._info['name_family']}"
    self._info['donation_is_anonymous'] = is_anon

    self.sync_to_db()
  
  def donation_amount(self, force=False):
    if force or not 'donation_amount' in self._info or self._info['donation_amount'] == None:
      self.recalculate_donation_info()
    return self._info['donation_amount']
  
  def donation_tier(self, force=False):
    if force or not 'donation_tier' in self._info or self._info['donation_tier'] == None:
      self.recalculate_donation_info()
    return self._info['donation_tier']
  
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
    affected_rows = Database.shared().execute(update_sql, update_args)

    if affected_rows == 0:
      insert_sql = f"INSERT INTO Attendees (badgefile_id, json, {','.join(keys)}) VALUES (?, ?, {', '.join(['?' for _ in keys])})"
      Database.shared().execute(insert_sql, base_args)

    if existing_id != self.id():
      # TODO: placeholder. we're going to want a column for the primary registrant's badgefile id.
      # if we changed someone's bfid, we need to make sure everyone who listed them as a primary registrant is updated to match.
      pass
  
  def ensure_attendee_table(self):
    Database.shared().execute("CREATE TABLE IF NOT EXISTS Attendees(badgefile_id INTEGER NOT NULL PRIMARY KEY, json TEXT NOT NULL)")
    defns_dict = { col[0]: col[1] for col in self.column_definitions() } 
    existing_cols = Database.shared().columns_of_table("Attendees")
    expected_cols = defns_dict.keys()
    missing_columns = list(set(expected_cols) - set(existing_cols))
    missing_defns = [[col, defns_dict[col]] for col in missing_columns if col in defns_dict]
    
    for defn in missing_defns:
      name, type = defn
      query = f"ALTER TABLE Attendees ADD COLUMN {name} {type} DEFAULT NULL;"
      Database.shared().execute(query)

  def column_definitions(self):
    return self.implicit_column_definitions() + self.explicit_column_definitions()

  def implicit_column_definitions(self):
    info = self.info()
    implicit_keys = info.keys() - self.explicit_column_definitions()
    if "badgefile_id" in implicit_keys:
      implicit_keys.remove("badgefile_id") # we manually handle this column outside of implicit_column_definitions and explicit_column_definitions
    if "json" in implicit_keys:
      implicit_keys.remove("json") # ditto
    
    # remove anything that is a list or dict; those can't go into the sqlite table
    implicit_keys = [k for k in implicit_keys if not isinstance(info[k], (list, dict))]

    return [ [key, "INTEGER" if isinstance(info[key], int) else "TEXT"] for key in implicit_keys ]

  def explicit_column_definitions(self):
    return [
    ]
  
  # return the attendee's current info, based on latest regdata with overrides applied
  def info(self):
    return self._info
  
  def web_info(self):
    web_info = self._info.copy()
    if "json" in web_info:
      del web_info["json"]
    return web_info

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
      # [9000, ["name_given", "name_family", "name_mi"]], # A pair of registrants both named "Sungjun Lee" broke this match.
      [9000, ["name_given", "name_family", "phone_mobile"]], # TODO: standardize phone numbers (both format AND source field)
      [9000, ["name_given", "name_family", "addr1", "postcode"]],

      # TODO: these don't really make sense...

      [50, ["name_family", "date_of_birth"]],
      [30, ["addr1", "postcode"]],
      [30, ["phone_mobile"]],
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
    # TODO: Strongly consider memoizing this!!
    return IssueManager.shared().open_issues_for_attendee(self)

  # return a list of previously identified issues regardless of status
  def all_issues(self):
    # TODO: Strongly consider memoizing this!!
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
      import time
      
      for filename in os.listdir(issue_dir):
        if "__" in filename:
          continue
        if filename.endswith(".py"):
          file_path = os.path.join(issue_dir, filename)
          
          # Measure import time
          start_import_time = time.time()
          
          # Dynamically import the script
          issue_type = filename[:-3]  # Strip .py extension
          spec = importlib.util.spec_from_file_location(issue_type, file_path)
          module = importlib.util.module_from_spec(spec)
          spec.loader.exec_module(module)
          
          import_time_ms = (time.time() - start_import_time) * 1000
          
          # Check for a function named 'run_check' and execute it
          if hasattr(module, "run_check"):
            start_check_time = time.time()
            issue_data = module.run_check(self)
            check_time_ms = (time.time() - start_check_time) * 1000
            total_time_ms = import_time_ms + check_time_ms
            if total_time_ms > 5.0:
              log.debug(f"Issue check {issue_type} execution completed in {check_time_ms:.2f} ms (total: {total_time_ms:.2f} ms)")
            if issue_data is not None:  # Only collect non-None results
              current_issues[issue_type] = issue_data
          elif total_time_ms > 5.0:
            log.debug(f"Issue check {issue_type} has no run_check function (import only: {import_time_ms:.2f} ms)")

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
  
  def party_meal_plan(self):
    meal_plans = [activity for activity in self.primary().activities() if activity.is_meal_plan() and activity.is_open()]
    return meal_plans[0] if len(meal_plans) > 0 else None
  
  def party_housing(self):
    return [activity for activity in self.primary().activities() if activity.is_housing() and activity.is_open()]
  
  def issue_categories(self):
    return list(set(json.loads(issue)['category'] for issue in self.open_issues().values()))
  
  def issues_in_category(self, category):
    issues = [json.loads(issue_raw) for issue_raw in self.open_issues().values()]
    for issue in issues:
      if 'category' not in issue:
        log.error(f"ERROR: Issue for attendee {self.id()} {self.full_name()} missing 'category' field: {issue}")
    return [issue for issue in issues if issue['category'] == category]
    
  # returns a list of reglist rows referring to this user
  def reglist_rows(self):
    return [x for x in Reglist.latest().rows() if x.attendee().id() == self.id()]
  
  # returns the latest ReglistRow for this user
  def latest_row(self):
    return self.reglist_rows()[-1]
  
  # boolean: is this the primary registrant?
  def is_primary(self):
    override = self.info().get("override_primary", None)
    if override == "false":
      return False
    return override == "true" or self.info()["is_primary"].lower() == "true"

  # force the attendee to have a given badgefile_id as their primary registrant
  def override_primary(self, value=True):
    if value is None:
      log.info(f"Clearing primary override for member {self.full_name()} {self.id()}")
      self._info["override_primary"] = None
    else:
      log.info(f"Marking member {self.full_name()} {self.id()} as {'primary' if value else 'non-primary'} by override.")
      self._info["override_primary"] = "true" if value else "false"
    self.sync_to_db()

  # set an override rating for an attendee; this is what will go on their badge and anywhere else we care about ratings
  def override_rating(self, value):
    if self._info.get("override_rating", None) != value:
      log.debug(f"Setting override rating for {self.full_name()}: {value if value else 'None'}")
      self._info["override_rating"] = value
      self.sync_to_db()

  def has_override_rating(self):
    return self._info.get("override_rating", None) is not None

  def set_ignore_tournament_issues(self, value):
    if self.has_ignore_tournament_issues() != value:
      log.debug(f"Setting ignore_tournament_issues for {self.full_name()}: {value}")
      self._info['ignore_tournament_issues'] = value
      self.sync_to_db()

  def has_ignore_tournament_issues(self):
    return self._info.get('ignore_tournament_issues', False)
  
  def set_will_arrange_own_housing(self, value):
    if self.will_arrange_own_housing() != value:
      log.debug(f"Setting will_arrange_own_housing for {self.full_name()}: {value}")
      self._info['will_arrange_own_housing'] = value
      self._info['will_arrange_own_housing_modified_at'] = datetime.now().isoformat()
      self.sync_to_db()

  def will_arrange_own_housing(self):
    return self._info.get('will_arrange_own_housing', False)
  
  # return self if is_primary, otherwise returns reference to primary registrant
  def primary(self):
    if self.is_primary():
      return self
    
    primary_registrant_id = self._info.get("primary_registrant_id")
    if primary_registrant_id:
      return self.badgefile().lookup_attendee(primary_registrant_id)
    
    return None

  def is_subject_to_youth_form(self):
    return self.age_at_congress() < 18
  
  def still_needs_youth_form(self):
    if not self.is_subject_to_youth_form():
      return False
    if not hasattr(self, '_youth_response'):
      from datasources.sheets.youth_form_responses import YouthFormResponses
      responses = YouthFormResponses(self._badgefile) # instantiation causes data pull, which should set youth form info for all attendees
      self.set_youth_info(responses.youth_form(self)) # defensively set ours again anyway, in case we're not in badgefile.attendees() for some reason
    
    if self._youth_response is None:
      return True
    
    # right now, we don't do anything to check for problems in the youth form -- if we can associate a youth to a form, then we have a youth form on file
    return False
  
  def mark_cancelled(self):
    self._info["status"] = "Cancelled"
    self.sync_to_db()
  
  def set_youth_info(self, response):
    self._youth_response = response

  
  def set_primary_registrant(self, primary_bfid):
    if primary_bfid != self._info.get("primary_registrant_id"):
      self._info["primary_registrant_id"] = primary_bfid
      self.sync_to_db()


  def set_housing_approval(self, approved):
    was_approved = self._info.get("housing_approved", False) == True

    if approved == was_approved:
      return

    ever_approved = self._info.get("housing_ever_approved", False) == True
    ever_disapproved = self._info.get("housing_ever_disapproved", False) == True

    self._info["housing_approved"] = approved
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if approved:
      log.info(f"Recording new housing approval for {self.id()}; housing_ever_approved={ever_approved}")
      self._info["housing_approval_time"] = now
      if not ever_approved:
        self._info["housing_first_approval_time"] = now
        self._info["housing_ever_approved"] = True
    else:
      log.info(f"Recording new housing disapproval for {self.id()}; housing_ever_disapproved={ever_disapproved}")
      self._info["housing_disapproval_time"] = now
      if not ever_disapproved:
        self._info["housing_first_disapproval_time"] = now
        self._info["housing_ever_disapproved"] = True
    
    self.sync_to_db()

  def is_housing_approved(self):
    return self.primary().info().get("housing_approved", False) == True
  
  def congress_payment_lines(self):
    if self.is_cancelled():
      return []
    
    from datasources.clubexpress.registration_fees_charges_congress import RegistrationFeesChargesCongress
    rfcc = RegistrationFeesChargesCongress.latest()
    btrn = rfcc.by_transrefnum()
    trn = self._info.get('transrefnum', None)
    if trn is None:
      log.warn(f'Non-cancelled attendee {self.full_name()} {self.id()} {self._info["status"]} has no Congress transrefnum')
      return []
    
    trn = int(trn)
    if not trn in btrn or len(btrn[trn]) == 0:
      log.warn(f'Non-cancelled attendee {self.full_name()} {self.id()} {self._info["status"]} has Congress transrefnum {trn}, but this is not in Registrant Fees and Charges')
      return []

    return btrn[trn]
  
  def congress_balance_due(self):
    payment_lines = self.congress_payment_lines()
    if len(payment_lines) > 0:
      return payment_lines[0]['balance_due']
    else:
      return 0
    
  def congress_total_fees(self):
    payment_lines = self.congress_payment_lines()
    if len(payment_lines) > 0:
      return payment_lines[0]['total_fees']
    else:
      return 0

  def housing_payment_lines(self):
    if self.is_cancelled():
      return []
    
    from datasources.clubexpress.registration_fees_charges_housing import RegistrationFeesChargesHousing
    rfch = RegistrationFeesChargesHousing.latest()
    housing_activities = self.party_housing()
    if not housing_activities:
      return []
    
    housing_trns = set()
    for activity in housing_activities:
      trn = activity.info().get('transrefnum')
      if trn is not None:
        housing_trns.add(int(trn))
    
    btrn = rfch.by_transrefnum()
    all_payment_lines = []
    for trn in housing_trns:
      if not trn in btrn:
        log.warn(f"Non-cancelled participant has housing transrefnum {trn}, but this is not in Registrant Fees and Charges")
      else:
        all_payment_lines += btrn[trn]

    return all_payment_lines
  
  def housing_total_fees(self):
    payment_lines = self.housing_payment_lines()
    seen_trns = set()
    total_fees = 0
    for line in payment_lines:
      if not line['transrefnum'] in seen_trns:
        seen_trns.add(line['transrefnum'])
        total_fees += line['total_fees']
    
    return total_fees

  def housing_balance_due(self):
    if self.is_cancelled():
      return 0

    payment_lines = self.housing_payment_lines()
    seen_trns = set()
    balance_due = 0
    for line in payment_lines:
      if not line['transrefnum'] in seen_trns:
        seen_trns.add(line['transrefnum'])
        balance_due += line['balance_due']
    
    return balance_due    

  
  def balance_due(self):
    return self.congress_balance_due() + self.housing_balance_due()


  def reglist_cacher(self):
    # this is a werid hack to make 2g_registration_duplicate work
    # (might not need this now that ce_report_base has latest implemented as a singleton)
    return ReglistCacher.shared()
  
class ReglistCacher:
  _instance = None
  
  @classmethod
  def shared(cls):
    if cls._instance is None:
      cls._instance = ReglistCacher()
    return cls._instance
  
  def __init__(self):
    self._reglist_rows_by_id = None

  def reglist_rows_by_id(self, reglist, badgefile):
    if self._reglist_rows_by_id is not None:
      return self._reglist_rows_by_id
    
    rrbid = {}
    reglist_rows = [row.info() for row in reglist.rows()]
    for row in reglist_rows:
      attendee = badgefile.find_attendee_from_report_row(row)
      if not attendee.id() in rrbid:
        rrbid[attendee.id()] = []
      rrbid[attendee.id()].append(row)

    self._reglist_rows_by_id = rrbid
    return self._reglist_rows_by_id