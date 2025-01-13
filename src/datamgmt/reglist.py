import os
import hashlib
import csv
from datetime import datetime
from io import StringIO

from .ce_integration import CEIntegration
from .report_manager import ReportManager
from .reglist_row import ReglistRow
from .google_drive import authenticate_service_account, upload_csv_to_drive

# Describes a single copy of the "reglist" -- the Registrant Data report from ClubExpress.

class Reglist:
  @classmethod
  def directory(cls):
    return "reports/RegistrantData"
  
  @classmethod
  # latest copy we pulled according to database
  def latest(cls):
    latest_info = ReportManager.shared().last_report_info("reglist")
    if latest_info == None:
      return None
    
    path = latest_info["path"]
    timestamp = "_".join(path.split("_")[-3:-1])
    
    try:
      with open(path, "rb") as file:
        csv = file.read()
        return cls(csv, timestamp)
    except FileNotFoundError:
      return None

  @classmethod
  # download a copy from CE, then save it to disk and return a copy
  def download(cls):
    uri = "https://usgo.org/popup.aspx?page_id=4036&club_id=454497&item_id=2472861"
    data = {
          "__EVENTTARGET": "ctl00$save_button",
          "ctl00$export_radiobuttonlist": "2",
          "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
          "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
      }
    
    csv = CEIntegration.shared().pull_report(uri, data)
    reglist = cls(csv)

    hash = reglist.hash()
    latest = Reglist.latest()
    if latest is not None:
      if latest.hash() == hash:
        # We don't need to save a copy if the report hasn't changed since last time.
        ReportManager.shared().pulled_report("reglist", hash, latest.path())
        existing = cls(csv)
        existing.path = latest.path()
        return existing

    reglist.save()
    reglist.upload_to_drive()
    ReportManager.shared().pulled_report("reglist", hash, reglist.path())

    return cls(csv)

  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self.header_row = None
    self._path = None
    self._hash = None

  def hash(self):
    if self._hash == None:
      self._hash = hashlib.sha256(self.csv).hexdigest()
    return self._hash
  
  def path(self):
    if self._path is None:
      shorthash = self.hash()[:8]
      self._path = f"{Reglist.directory()}/RegistrantData_{self.timestamp}_{shorthash}.csv"
    return self._path
  
  def is_latest(self):
    return ReportManager.shared().last_report_info("reglist")["hash"] == self.hash()
  
  def save(self):
    os.makedirs(Reglist.directory(), exist_ok=True)
    with open(self.path(), "w") as file:
      file.write(self.csv.decode("utf-8"))

  def upload_to_drive(self):
    service_account_file = os.path.expanduser("~/gocongress2025-0f356f9df4e4.json")
    folder_id = "1AnJeOujx1j2-RGvkJsQWp_2tqe5g2V-F"
    service = authenticate_service_account(service_account_file)
    upload_csv_to_drive(service, self.path(), "registrant_data.csv", folder_id)

  
  def header(self):
    if self.header_row == None:
      self.header_row = next(csv.reader(StringIO(self.csv.decode("utf-8")), None))
    return self.header_row
  
  # return a list of all ReglistRows in this Reglist
  def rows(self):
    return [ReglistRow(self, row) for row in csv.reader(StringIO(self.csv.decode("utf-8")))][1:]
  
  def index_for_field(self, field_name):
    map = self.heading_map()
    heading = map[field_name].lower()
    for i, string in enumerate(self.header()):
      if string.lower() == heading:
        return i
    return None
  
  def heading_map(self):
    return {
      "event_title": "Title",
      "regtime": "Date/Time",
      "status": "Status",
      "transrefnum": "Trans. Ref. Num.",
      "registrant_fees": "Registrant Fees",
      "name_given": "First Name",
      "name_mi": "Middle Initial",
      "name_family": "Last Name",
      "name_nickname": "Nickname",
      "email": "Email",
      "phone_a": "Phone",
      "addr1": "Address 1",
      "addr2": "Address 2",
      "city": "City",
      "state": "State",
      "postcode": "Postal Code",
      "country": "Country",
      "company": "Company",
      "phone_cell": "Cell Phone",
      "job_title": "Work Title",
      "is_primary": "Primary Member?",
      "is_member": "Member?",
      "aga_id": "Member Number",
      "regtype": "Registrant Type",
      "primary_registrant_name": "Primary Registrant Name",
      "seqno": "Sequence Number",
      "signed_datetime": "Signed Datetime",
      "state": "State",
      "state_comments": "State Comments",
      "country": "Country",
      "country_comments": "Country Comments",
      "date_of_birth": "Date of Birth",
      "date_of_birth_comments": "Date of Birth Comments",
      "tshirt": "Tshirt",
      "tshirt_comments": "Tshirt Comments",
      "rank_playing": "Playing Rank",
      "rank_comments": "Playing Rank Comments",
      "tournaments": "Tournaments",
      "tournaments_comments": "Tournaments Comments",
      "phone_mobile": "Mobile Phone",
      "phone_mobile_comments": "Mobile Phone Comments",
      "emergency_contact_name": "Emergency Contact Name",
      "emergency_contact_comments": "Emergency Contact Name Comments",
      "emergency_contact_phone": "Emergency Contact Phone Number",
      "emergency_contact_phone_comments": "Emergency Contact Phone Number Comments",
      "emergency_contact_email": "Emergency Contact Email",
      "emergency_contact_email_comments": "Emergency Contact Email Comments",
      "emergency_contact_": "Youth under 18  Adult at Congress",
      "youth_adult_at_congress": "Youth under 18  Adult at Congress Comments",
      "youth_adult_type": "Youth under 18  Adult Type",
      "youth_adult_type_comments": "Youth under 18  Adult Type Comments",
      "languages": "Languages",
      "languages_comments": "Languages Comments",
      "translator": "Translator",
      "translator_comments": "Translator Comments",
      "admin1": "Admin 1",
      "admin1_comments": "Admin 1 Comments",
    }
