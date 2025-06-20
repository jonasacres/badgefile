from integrations.database import Database
from .attendee import Attendee
from .id_manager import IdManager
from datasources.clubexpress.reglist import Reglist
from datasources.clubexpress.activity_list import ActivityList
from datasources.clubexpress.activity import Activity
from datasources.clubexpress.housing_activity_list import HousingActivityList
from datasources.sheets.attendee_status import AttendeeStatusSource
from datasources.clubexpress.housing_reglist import HousingReglist
from datasources.clubexpress.payments_report import PaymentsReport
from datasources.tdlist import TDList
from artifacts.generated_reports.issue_sheet import IssueSheet
from artifacts.generated_reports.donor_report import DonorReport
from artifacts.generated_reports.attendee_info import AttendeeInfo
from artifacts.generated_reports.reg_history_report import RegHistoryReport
from artifacts.generated_reports.as_overview import OverviewReport
from artifacts.generated_reports.as_housing_registrations import HousingRegistrationsReport
from artifacts.generated_reports.as_housing_assignments import HousingAssignmentsReport
from artifacts.generated_reports.as_email import EmailReport
from artifacts.generated_reports.as_tournaments_report import TournamentsReport
from artifacts.generated_reports.as_membership_report import MembershipReport
from artifacts.generated_reports.as_payment_report import PaymentReport
from artifacts.generated_reports.as_other_issues import OtherIssuesReport
from artifacts.generated_reports.as_aggregate import AggregateReport
from artifacts.emails.housing_approval import HousingApprovalEmail
from artifacts.html.friends_of_congress_page import DonorPage
from integrations.google_api import authenticate_service_account, upload_json_to_drive
from util.secrets import secret
from log.logger import log
from model.registrar_sheet import RegistrarSheet

import json
import os
import time
import yaml

class Badgefile:
  """Encapsulates the master view of the Badgefile, which lists all Attendees at the Go Congress."""

  def __init__(self):
    self._attendees = None
    self._parties = None
    self._override_map = None

  def path(self):
    return "artifacts/badgefile.json"

  def run_approvals(self):
    sheet = RegistrarSheet(self)
    sheet.update_from_housing_registration()
    HousingApprovalEmail(self).send()
    EmailReport(self).update()

  def update(self):
    AttendeeStatusSource(self).read_tournament_overrides()
    self.update_attendees()
    self.update_raw_reports()
    self.update_attendee_status_sheet()

    self.generate_json()
    self.upload()

  def update_attendees(self):
    log.debug("Updating badgefile")
    reglist_rows = self.active_reglist_rows()
    for row in reglist_rows:
      self.update_or_create_attendee_from_reglist_row(row)
    self.prune_silent_cancellations(reglist_rows)
    
    for attendee in self.attendees():
      attendee.hash_id() # force calculation of hash_id. TODO: this is hideous, but it fixes a bug I need fixed ASAP
      attendee.invalidate_activities()
    
    # by doing the ActivityList/HousingActivityList.latest().rows(), we ensure all the current rows are in the DB
    # problem: if someone cancels an event manually in CE, the row is deleted from the report, and not marked as cancelled
    # so we have to list all the activity_registrant_ids that are in the sheets, then hand them to a method that deletes anything in the Activities tables not in that list
    all_act_ids  = [act.info()['activity_registrant_id'] for act in ActivityList.latest().rows(self) if act is not None] # merely asking for the rows causes them to be saved to the DB
    all_act_ids += [act.info()['activity_registrant_id'] for act in HousingActivityList.latest().rows(self) if act is not None] # also force housing rows to DB
    Activity.prune_to_activity_registrant_ids(all_act_ids)
    
    TDList.latest().apply(self) # Now go apply ratings/expiration dates/chapters from the TD list
    
    log.debug("Ensuring consistency...")
    start_time = time.time()
    self.ensure_consistency()
    elapsed_ms = (time.time() - start_time) * 1000
    log.debug(f"Consistency check completed in {elapsed_ms:.2f} ms")

    log.debug("Populating derived fields...")
    start_time = time.time()
    for attendee in self.attendees():
      attendee.populate_derived_fields()
    elapsed_ms = (time.time() - start_time) * 1000
    log.debug(f"Populating derived fields completed in {elapsed_ms:.2f} ms")

    log.debug("Scanning attendees for issues...")
    start_time = time.time()
    for attendee in self.attendees():
      log.trace(f"Checking {attendee.full_name()}")
      attendee.scan_issues()
    log.debug(f"Scanning attendees for issues completed in {elapsed_ms:.2f} ms")
  
  def update_raw_reports(self):
    IssueSheet(self).generate("artifacts/issue_sheet.csv")
    DonorReport(self).generate("artifacts/donor_report.csv")
    AttendeeInfo(self).generate("artifacts/attendee_info.csv")
    RegHistoryReport(self).generate("artifacts/reg_history_report.csv")
    DonorPage(self).generate().upload()
 
  def update_attendee_status_sheet(self):
    AggregateReport(self).update()
    OverviewReport(self).update()
    HousingRegistrationsReport(self).update()
    HousingAssignmentsReport(self).update()
    EmailReport(self).update()
    TournamentsReport(self).update()
    MembershipReport(self).update()
    PaymentReport(self).update()
    OtherIssuesReport(self).update()
    
  def generate_json(self):
    # Create artifacts directory if it doesn't exist
    log.debug(f"badgefile: Generating badgefile export at {self.path()}")
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
    log.debug("badgefile: Uploading to Google Drive")
    service = authenticate_service_account()
    upload_json_to_drive(service, self.path(), "badgefile.json", secret("folder_id"))

  def lookup_attendee(self, badgefile_id):
    if badgefile_id is None:
      return None
    
    badgefile_id = int(badgefile_id)
    for attendee in self.attendees():
      if attendee.id() == badgefile_id:
        return attendee

    override_map = self.override_map()   
    if badgefile_id in override_map:
      badgefile_id = override_map[badgefile_id]
    for attendee in self.attendees():
      if attendee.id() == badgefile_id:
        return attendee
    
    return None

  def override_map(self, force=False):
    if self._override_map is None or force:
      if os.path.exists("override_map.yaml"):
        with open("override_map.yaml", "r") as f:
          self._override_map = yaml.safe_load(f)
      else:
        self._override_map = {}
    return self._override_map

  def lookup_attendee_by_hash_id(self, hash_id):
    for attendee in self.attendees():
      if attendee.hash_id() == hash_id:
        return attendee
    
    return None
  
  # return list of all attendees
  def attendees(self, force_refresh=False):
    if self._attendees is None or force_refresh:
      log.debug("badgefile: Loading attendees list")
      Attendee(self).ensure_attendee_table() # shouldn't be instance method of Attendee
      rows = Database.shared().query("SELECT * FROM Attendees")
      self._attendees = [Attendee(self).load_db_row(row) for row in rows]
      self.ensure_consistency()
      log.debug(f"badgefile: Loaded {len(self._attendees)} attendees")
    return self._attendees
  
  def parties(self):
    if self._parties is None:
      log.debug("badgefile: Organizing party lists")
      parties = {}
      for attendee in self._attendees:
        if not attendee.primary() in parties:
          parties[attendee.primary()] = []
        party = parties[attendee.primary()]
        party.append(attendee)
      self._parties = parties
    return self._parties
  
  # returns an Attendee corresponding to the user in the reglist if one exists, or None
  # if none exists.
  def find_attendee_from_report_row(self, row):
    badgefile_id = IdManager.shared().lookup_reg_info(row)

    if badgefile_id != None:
      canonical_id = IdManager.shared().canonical_id(badgefile_id)
      for attendee in self.attendees():
        if IdManager.shared().canonical_id(attendee.id()) == canonical_id:
          return attendee
      
      log.debug(f"Attendee has badgefile_id {badgefile_id}, but no attendee matches.", data=row)
      return None

    scored = [ [attendee, attendee.similarity_score(row)] for attendee in self.attendees() ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # no attendees yet
    if len(scored) == 0:
      log.debug(f"No existing member matches '{row['name_given']} {row['name_family']}', born {row['date_of_birth']}")
      return None
    
    best_score = scored[0][1]
    delta = scored[0][1] - scored[1][1] if len(scored) >= 2 else best_score

    # TODO: 100 chosen arbitrarily for both conditions below; think this through or find through trial and error
    # honestly the score system probably sucks as a general concept
    if best_score < 100 or delta < 100:
      log.debug(f"No existing member matches '{row['name_given']} {row['name_family']}', born {row['date_of_birth']}")
      return None
    
    log.debug(f"Existing member matches '{row['name_given']} {row['name_family']}', born {row['date_of_birth']}, mobile {row['phone_mobile']}: ID {scored[0][0].id()}, score {scored[0][1]}")
    return scored[0][0]
  
  def active_reglist_rows(self):
    by_attendee = {}
    rows = Reglist.latest().rows()
    for i, row in enumerate(rows):
      row_num = i + 2 # convert to excel-style row number, understanding that it is one-based and has a header row
      attendee = self.find_attendee_from_report_row(row.info())
      if attendee is None:
        attendee = Attendee(self)
        attendee.load_reglist_row(row, sync=False)
      if not attendee.id() in by_attendee:
        by_attendee[attendee.id()] = [row_num, row]
      elif by_attendee[attendee.id()][1].info()['status'] == "Cancelled" and row.info()['status'] != "Cancelled":
        log.debug(f"Replacing cancelled row {by_attendee[attendee.id()][0]} with active row {row_num} for attendee {attendee.id()} {attendee.full_name()}")
        by_attendee[attendee.id()] = [row_num, row]
      else:
        log.debug(f"Keeping existing row {by_attendee[attendee.id()][0]} in favor of cancelled row {row_num} for attendee {attendee.id()} {attendee.full_name()}")
    
    filtered = list([x[1] for x in by_attendee.values()])
    log.info(f"Filtered list of {len(rows)} down to {len(filtered)} unique attendees")
    return filtered
  
  def prune_silent_cancellations(self, rows):
    # In certain cases, registrations can be cancelled in ClubExpress and the entire registration will be deleted from the reglist,
    # instead of being marked as cancelled. We want to make sure we mark any leftover 'ghost' records as cancelled. We can spot them because
    # they have transrefnums that don't appear in the current reglist.

    trns = set()
    for row in rows:
      trn = row.info().get('transrefnum', None)
      if trn:
        trns.add(int(trn))
    
    prunable = [att for att in self.attendees() if not att.is_cancelled() and int(att.info()['transrefnum']) not in trns]
    for attendee in prunable:
      log.info(f"Marking attendee {attendee.id()} {attendee.full_name()} as cancelled, as transrefnum {attendee.info()['transrefnum']} is not in current reglist")
      attendee.mark_cancelled()
  
  # returns an Attendee corresponding to the user in the reglist. uses an existing Attendee
  # if one exists; otherwise, creates one.
  def update_or_create_attendee_from_reglist_row(self, row):
    attendee = self.find_attendee_from_report_row(row.info())
    if attendee != None:
      attendee.load_reglist_row(row, True)
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
      try:
        primary_bfid = self.locate_primary_for_attendee(attendee).id()
        attendee.set_primary_registrant(primary_bfid)
      except Exception as exc:
        log.warn(f"Encountered an exception finding primary registrant for {attendee.full_name()}", exception=exc)
  
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
    candidates = [att for att in self.attendees() if f"{att.info()['name_given']} {att.info()['name_family']}" == prn and att.is_primary()]
    if len(candidates) == 1:
      # we found exactly one match, which is the best outcome.
      return candidates[0]
    elif len(candidates) == 0:
      # no matches; this is bad!! we'll do the best we can by treating the attendee as their own primary.
      # CE does actually produce this case; see 2025's May 2nd transaction 7717 in the registrant data for an example.
      log.notice(f"Unable to locate primary registrant for attendee {attendee.info()['name_given']} {attendee.info()['name_family']} ({attendee.info()['badgefile_id']}); searched for name '{prn}' and/or transrefnum '{transrefnum}'. Treating as own primary registrant.")
      attendee.override_primary()
      return attendee
    else:
      # multiple matches; very bad!! needs manual solution.
      log.warn(f"Found multiple possible primary registrants for attendee {attendee.info()['name_given']} {attendee.info()['name_family']} ({attendee.info()['badgefile_id']}); searched for name '{prn}', found {len(candidates)} matches")
      return None

