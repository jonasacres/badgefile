import csv
import re
from datetime import datetime
from io import StringIO

from .activity import Activity
from .ce_report_base import CEReportBase
from log.logger import *
# Describes a single copy of the "activity list" -- the Activity Registrant Data report from ClubExpress.

class ActivityList(CEReportBase):
  @classmethod
  def report_key(cls):
    return "activity_list"

  @classmethod
  def report_uri(cls):
    return "https://usgo.org/popup.aspx?page_id=4036&club_id=454497&item_id=2516874"
  
  @classmethod
  def report_data(cls):
    return {
      "__EVENTTARGET": "ctl00$save_button",
      "ctl00$export_radiobuttonlist": "3",
      "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
      "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open,+Paid,+Cancelled,+Not+paid+in+time+limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
    }
  
  @classmethod
  def google_drive_name(cls):
    return "activity_registrant_data.csv"
  
  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self.header_row = None
    self._path = None
    self._hash = None

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
    elif re.match(r'^-?[0-9]+(\.[0-9]+)$', raw_value):
      # Check if it's a float or int, handling negative numbers
      try:
        return float(raw_value) if "." in raw_value else int(raw_value)
      except ValueError:
        return raw_value
    else:
      return raw_value  # Use the original string if it's not numeric
  
  def heading_map(self):
    return {
      "event_title":                          "Title",
      "regtime":                              "Date/Time",
      "status":                               "Status",
      "transrefnum":                          "Trans. Ref. Num.",
      "activity_fee":                         "Activity Fee",
      "registrant_fees":                      "Registrant Fees",
      "name_given":                           "First Name",
      "name_mi":                              "Middle Initial",
      "name_family":                          "Last Name", 
      "name_nickname":                        "Nickname",
      "email":                                "Email",
      "phone_a":                              "Phone",
      "addr1":                                "Address 1",
      "addr2":                                "Address 2",
      "city":                                 "City",
      "state":                                "State",
      "postcode":                             "Postal Code",
      "country":                              "Country",
      "company":                              "Company",
      "phone_cell":                           "Cell Phone",
      "job_title":                            "Work Title",
      "is_primary":                           "Primary Member?",
      "is_member":                            "Member?",
      "aga_id":                               "Member Number",
      "regtype":                              "Registrant Type",
      "primary_registrant_name":              "Primary Registrant Name",
      "signed_datetime":                      "Signed Datetime",
      "activity_type":                        "Activity Type",
      "activity_title":                       "Activity Title",
      "activity_datetime":                    "Activity Date/Time",
      "capacity_limited":                     "Capacity Limited?",
      "capacity":                             "Capacity",
      "activity_registrant_id":               "Activity Registrant id",
      "activity_seqno":                       "Activity Sequence Number",
      "attended":                             "Attended?",
      "partial_week_instructions":            "Partial Week Instructions",
      "partial_week_instructions_comments":   "Partial Week Instructions Comments",
      "partial_week_first_day":               "Partial Week  First Day",
      "partial_week_first_day_comments":      "Partial Week  First Day Comments",
      "partial_week_last_day":                "Partial Week  Last Day",
      "partial_week_last_day_comments":       "Partial Week  Last Day Comments",
    }
