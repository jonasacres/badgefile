import csv
from datetime import datetime
from io import StringIO

from .ce_report_base import CEReportBase
from .reglist_row import ReglistRow
from util.secrets import secret

class Reglist(CEReportBase):
  """Describes a single copy of the "reglist" -- the Registrant Data report from ClubExpress. This report describes each
  individual Congress attendee registration."""
  @classmethod
  def report_key(cls):
    return "registrant_data"

  @classmethod
  def report_uri(cls):
    return secret('congress_event_url')
  
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
    return "registrant_data.csv"
  
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
      "status":                         "Status", 
      "transrefnum":                    "Trans. Ref. Num.",
      "registrant_fees":                "Registrant Fees",
      "name_given":                     "First Name",
      "name_mi":                        "Middle Initial", 
      "name_family":                    "Last Name",
      "name_nickname":                  "Nickname",
      "email":                          "Email",
      "phone_a":                        "Phone",
      "addr1":                          "Address 1",
      "addr2":                          "Address 2", 
      "city":                           "City",
      "state":                          "State",
      "postcode":                       "Postal Code",
      "country":                        "Country",
      "company":                        "Company",
      "phone_cell":                     "Cell Phone",
      "job_title":                      "Work Title",
      "is_primary":                     "Primary Member?",
      "is_member":                      "Member?",
      "aga_id":                         "Member Number",
      "regtype":                        "Registrant Type",
      "primary_registrant_name":        "Primary Registrant Name",
      "seqno":                          "Sequence Number",
      "signed_datetime":                "Signed Datetime",
      "state":                          "State",
      "state_comments":                 "State Comments",
      "country":                        "Country",
      "country_comments":               "Country Comments", 
      "date_of_birth":                  "Date of Birth",
      "date_of_birth_comments":         "Date of Birth Comments",
      "tshirt":                         "Tshirt",
      "tshirt_comments":                "Tshirt Comments",
      "rank_playing":                   "Playing Rank",
      "rank_comments":                  "Playing Rank Comments",
      "tournaments":                    "Tournaments",
      "tournaments_comments":           "Tournaments Comments",
      "phone_mobile":                   "Mobile Phone",
      "phone_mobile_comments":          "Mobile Phone Comments",
      "emergency_contact_name":         "Emergency Contact Name",
      "emergency_contact_comments":     "Emergency Contact Name Comments",
      "emergency_contact_phone":        "Emergency Contact Phone Number",
      "emergency_contact_phone_comments": "Emergency Contact Phone Number Comments",
      "emergency_contact_email":        "Emergency Contact Email",
      "emergency_contact_email_comments": "Emergency Contact Email Comments",
      "emergency_contact_":             "Youth under 18  Adult at Congress",
      "youth_adult_at_congress":        "Youth under 18  Adult at Congress Comments",
      "youth_adult_type":               "Youth under 18  Adult Type",
      "youth_adult_type_comments":      "Youth under 18  Adult Type Comments",
      "languages":                      "Languages",
      "languages_comments":             "Languages Comments",
      "translator":                     "Translator",
      "translator_comments":            "Translator Comments",
      "admin1":                         "Admin 1",
      "admin1_comments":                "Admin 1 Comments",
    }
