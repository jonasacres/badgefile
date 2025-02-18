import csv
import re
from datetime import datetime
from io import StringIO
from util.secrets import secret

from .activity import Activity
from .ce_report_base import CEReportBase
from log.logger import log

class HousingActivityList(CEReportBase):
  """Describes a single copy of the "housing activity list" -- the Housing Activity Registrant Data report from ClubExpress. This report
  shows each line-item that every participant has purchased within an event (e.g. admission fee, banquet, donation)"""
  
  @classmethod
  def report_key(cls):
    return "housing_activity_list"

  @classmethod
  def report_uri(cls):
    return secret("housing_event_url")
  
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
    return "housing_activity_registrant_data.csv"
  
  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self.header_row = None
    self._path = None
    self._hash = None

  # return a list of all Activities in this HousingActivityList
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
      "roommate_a":                           "Roommate Selection a",
      "roommate_a_comments":                  "Roommate Selection a Comments",
      "roommate_b":                           "Roommate Selection b",
      "roommate_b_comments":                  "Roommate Selection b Comments",
      "roommate_c":                           "Roommate Selection c",
      "roommate_c_comments":                  "Roommate Selection c Comments"
    }
