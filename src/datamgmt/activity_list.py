import os
import hashlib
import csv
from datetime import datetime
from io import StringIO

from .ce_integration import CEIntegration
from .report_manager import ReportManager
from .activity import Activity
from .google_drive import authenticate_service_account, upload_csv_to_drive

# TODO: subclass both this and reglist from a common base class
# Describes a single copy of the "activity list" -- the Activity Registrant Data report from ClubExpress.

class ActivityList:
  @classmethod
  def directory(cls):
    return "reports/ActivityRegistrantData"
  
  @classmethod
  # latest copy we pulled according to database
  def latest(cls):
    latest_info = ReportManager.shared().last_report_info("activity_list")
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
          "ctl00$export_radiobuttonlist": "3",
          "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
          "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
      }
    
    csv = CEIntegration.shared().pull_report(uri, data)
    activity_list = cls(csv)

    hash = activity_list.hash()
    latest = ActivityList.latest()
    if latest is not None:
      if latest.hash() == hash:
        # We don't need to save a copy if the report hasn't changed since last time.
        ReportManager.shared().pulled_report("activity_list", hash, latest.path())
        existing = cls(csv)
        existing.path = latest.path()
        return existing

    activity_list.save()
    activity_list.upload_to_drive()
    ReportManager.shared().pulled_report("activity_list", hash, activity_list.path())

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
      self._path = f"{ActivityList.directory()}/ActivityRegistrantData_{self.timestamp}_{shorthash}.csv"
    return self._path
  
  def is_latest(self):
    return ReportManager.shared().last_report_info("activity_list")["hash"] == self.hash()
  
  def save(self):
    os.makedirs(ActivityList.directory(), exist_ok=True)
    with open(self.path(), "w") as file:
      file.write(self.csv.decode("utf-8"))

  def upload_to_drive(self):
    service_account_file = "/home/jonas/gocongress2025-0f356f9df4e4.json"
    folder_id = "1AnJeOujx1j2-RGvkJsQWp_2tqe5g2V-F"
    service = authenticate_service_account(service_account_file)
    upload_csv_to_drive(service, self.path(), "activity_registrant_data.csv", folder_id)

  
  def header(self):
    if self.header_row == None:
      self.header_row = next(csv.reader(StringIO(self.csv.decode("utf-8")), None))
    return self.header_row
  
  # return a list of all Activities in this ActivityList
  def rows(self, badgefile):
    raw_rows = csv.reader(StringIO(self.csv.decode("utf-8")))
    next(raw_rows) # skip past the header row

    index_map = {key: self.index_for_field(key) for key in self.heading_map()}
    activities = []

    for row in raw_rows:
      translated_row = {field: self.translate_value(field, row[index_map[field]]) for field in index_map.keys()}
      activity = Activity.with_report_row(badgefile, translated_row)
      activities.append(activity)
    
    return activities
  
  def translate_value(self, field, raw_value):
    if "phone" in field or field == "postcode":
      return raw_value # ensure these remain as strings, even if they happen to have been written exclusively with numerics
    elif raw_value == "":
      return None  # Blank string becomes None
    elif raw_value.replace(".", "", 1).isdigit():
      # Check if it's a float or int
      return float(raw_value) if "." in raw_value else int(raw_value)
    else:
      return raw_value  # Use the original string if it's not numeric

  
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
      "activity_fee": "Activity Fee",
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
      "signed_datetime": "Signed Datetime",
      "activity_type": "Activity Type",
      "activity_title": "Activity Title",
      "activity_datetime": "Activity Date/Time",
      "capacity_limited": "Capacity Limited?",
      "capacity": "Capacity",
      "activity_registrant_id": "Activity Registrant id",
      "activity_seqno": "Activity Sequence Number",
      "attended": "Attended?",
      "partial_week_instructions": "Partial Week Instructions",
      "partial_week_instructions_comments": "Partial Week Instructions Comments",
      "partial_week_date_range": "Partial Week Date Range",
      "partial_week_date_range_comments": "Partial Week Date Range Comments",
    }
