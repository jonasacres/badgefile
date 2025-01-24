from integrations.database import Database
from .attendee import Attendee
from .id_manager import IdManager
from .clubexpress.reglist import Reglist
from .clubexpress.activity_list import ActivityList
from .tdlist import TDList
from .generated_reports.issue_sheet import IssueSheet
from .generated_reports.donor_report import DonorReport
from .generated_reports.reg_history_report import RegHistoryReport
from integrations.google_api import authenticate_service_account, upload_json_to_drive
from util.secrets import secret

import json
import os

# Encapsulates the master view of the Badgefile, which lists all Attendees at the Go Congress.
class Badgefile:
  def __init__(self):
    self._attendees = None
    self.db = Database.shared()

  def path(self):
    return "artifacts/badgefile.json"

  def update(self):
    # TODO: when does this become a "download"?
    for row in Reglist.latest().rows():
      self.update_or_create_attendee_from_reglist_row(row)
    
    for attendee in self.attendees():
      attendee.invalidate_activities()
    ActivityList.latest().rows(self) # merely asking for the rows causes them to be saved to the DB
    
    TDList.latest().apply(self) # Now go apply ratings/expiration dates/chapters from the TD list
    
    self.ensure_consistency()
    for attendee in self.attendees():
      attendee.populate_derived_fields()
      attendee.scan_issues()
    
    IssueSheet(self).generate("reports/issue_sheet.csv")
    DonorReport(self).generate("reports/donor_report.csv")
    RegHistoryReport(self).generate("reports/reg_history_report.csv")

    self.generate_json()
    # self.upload()
    
  def generate_json(self):
    # Create artifacts directory if it doesn't exist
    os.makedirs("artifacts", exist_ok=True)

    # Generate JSON data for all non-cancelled attendees
    attendees_data = []
    for attendee in self.attendees():
      attendee.populate_derived_fields()
      info = attendee.info()
      info["phone_canonical"] = attendee.phone()
      info["tournaments_canonical"] = attendee.tournaments()
      info["languages_canonical"] = attendee.languages()
      attendees_data.append(attendee.info())

    # Write JSON file
    with open(self.path(), "w") as f:
      json.dump({"attendees": attendees_data}, f, indent=2)
  
  def upload(self):
    service = authenticate_service_account()
    upload_json_to_drive(service, self.path(), "badgefile.json", secret("folder_id"))

  def lookup_attendee(self, badgefile_id):
    for attendee in self.attendees():
      if attendee.id() == badgefile_id:
        return attendee
    return None
  
  # return list of all attendees
  def attendees(self):
    if self._attendees is None:
      Attendee(self).ensure_attendee_table() # shouldn't be instance method of Attendee
      rows = self.db.query("SELECT * FROM Attendees")
      self._attendees = [Attendee(self).load_db_row(row) for row in rows]
      self.ensure_consistency()
    return self._attendees
  
  # returns an Attendee corresponding to the user in the reglist if one exists, or None
  # if none exists.
  def find_attendee_from_report_row(self, row):
    badgefile_id = IdManager.shared().lookup_reg_info(row)

    if badgefile_id != None:
      canonical_id = IdManager.shared().canonical_id(badgefile_id)
      for attendee in self.attendees():
        if IdManager.shared().canonical_id(attendee.id()) == canonical_id:
          return attendee
      
      # TODO: Scary log message here! The attendee has a badgefile_id, but we can't find any attendees who actually have that ID.
      return None

    scored = [ [attendee, attendee.similarity_score(row)] for attendee in self.attendees() ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # no attendees yet
    if len(scored) == 0:
      return None
    
    best_score = scored[0][1]
    delta = scored[0][1] - scored[1][1] if len(scored) >= 2 else best_score

    # TODO: 100 chosen arbitrarily for both conditions below; think this through or find through trial and error
    # honestly the score system probably sucks as a general concept
    if best_score < 100:
      return None
    if delta < 100:
      return None
    
    return scored[0][0]
  
  # returns an Attendee corresponding to the user in the reglist. uses an existing Attendee
  # if one exists; otherwise, creates one.
  def update_or_create_attendee_from_reglist_row(self, row):
    attendee = self.find_attendee_from_report_row(row.info())
    if attendee != None:
      attendee.load_reglist_row(row)
      return attendee
    
    # no good matches; create a new attendee
    attendee = Attendee(self).load_reglist_row(row)
    self._attendees.append(attendee)
    return attendee
  
  def ensure_consistency(self):
    self.correlate_primary_registrants()
  
  def correlate_primary_registrants(self):
    # go through all attendees, and make sure we set the primary registrant for each.
    for attendee in self.attendees():
      primary_bfid = self.locate_primary_for_attendee(attendee).id()
      attendee.set_primary_registrant(primary_bfid)
  
  def locate_primary_for_attendee(self, attendee):
    # easiest case: the attendee is marked as the primary for a registration. no searching needed!
    if attendee.is_primary():
      return attendee
    
    # most people's primaries have the same transrefnum, so see if we can find a primary registrant who matches transrefnum
    transrefnum = attendee.info()["transrefnum"]
    for att in self.attendees():
      if att.info()["transrefnum"] != transrefnum:
        continue
      if not att.is_primary():
        continue

      # found primary registrant for this transaction
      return att
    
    # sometimes people are non-primary registrants on a different transaction, so now we have to try to match on primary_registrant_name
    # primary_registrant_name is based on "%s %s" % (first_name, last_name) so look for that
    prn = attendee.info()["primary_registrant_name"]
    candidates = [att for att in self.attendees() if f"{att.info()['name_given']} {att.info()['name_family']}" == prn]
    if len(candidates) == 1:
      # we found exactly one match, which is the best outcome.
      return candidates[0]
    elif len(candidates) == 0:
      # no matches; this is bad!! we have to manually solve this.
      # TODO: scary log message
      return None
    else:
      # multiple matches; also very bad!! needs manual solution.
      # TODO: scary log message
      return None

