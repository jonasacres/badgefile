import csv
from datetime import datetime
from io import StringIO

from .ce_report_base import CEReportBase
from .reglist_row import ReglistRow
from util.secrets import secret

class HousingReglist(CEReportBase):
  """Describes a single copy of the "reglist" -- the Registrant Data report from ClubExpress. This report describes each
  individual Congress attendee registration."""
  @classmethod
  def report_key(cls):
    return "housing_registrant_data"

  @classmethod
  def report_uri(cls):
    return secret('housing_event_url')
  
  @classmethod
  def report_data(cls):
    return {
      "__EVENTTARGET": "ctl00$save_button",
      "ctl00$export_radiobuttonlist": "2",
      "ctl00$registration_status_dropdown": "Open, Paid, Cancelled, Not paid in time limit",
      "ctl00_registration_status_dropdown_ClientState": '{"logEntries":[],"value":"","text":"Open, Paid, Cancelled, Not paid in time limit","enabled":true,"checkedIndices":[0,1,2,3],"checkedItemsTextOverflows":false}'
    }

  @classmethod
  def google_drive_name(cls):
    return "housing_registrant_data.csv"
  
  def __init__(self, csv, timestamp=None):
    if timestamp == None:
      timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    self.timestamp = timestamp
    self.csv = csv
    self.header_row = None
    self._path = None
    self._hash = None

  # return a list of all ReglistRows in this Reglist
  def rows(self):
    return [ReglistRow(self, row) for row in csv.reader(StringIO(self.csv.decode("utf-8")))][1:]
    
  def heading_map(self):
    return {
      "event_title":                    "Title",
      "regtime":                        "Date/Time",
      "registrant_fees":                "Registrant Fees",
      "status":                         "Status", 
      "transrefnum":                    "Trans. Ref. Num.",
      "name_given":                     "First Name",
      "name_mi":                        "Middle Initial", 
      "name_family":                    "Last Name",
      "name_nickname":                  "Nickname",
      "aga_id":                         "Member Number",
      "email":                          "Email",
      "phone_a":                        "Phone",
      "addr1":                          "Address 1",
      "addr2":                          "Address 2", 
      "city":                           "City",
      "state":                          "State",
      "postcode":                       "Postal Code",
      "country":                        "Country",
      "company":                        "Company",
      "job_title":                      "Work Title",
      "phone_cell":                     "Cell Phone",
      "is_primary":                     "Primary Member?",
      "companion_count":                "Companion Count",
      "is_member":                      "Member?",
      "regtype":                        "Registrant Type",
      "seqno":                          "Sequence Number",
      "event_reg_link":                 "Link to event Registration",
      "event_reg_link_comments":        "Link to event Registration Comments",
      "admin2":                         "Admin 2",
      "admin2_comments":                "Admin 2 Comments",      
    }
