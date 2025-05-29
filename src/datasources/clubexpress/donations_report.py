import csv
import re
from datetime import datetime
from io import StringIO
from util.secrets import secret

from .activity import Activity
from .ce_report_base import CEReportBase
from log.logger import log

class DonationsReport(CEReportBase):
  @classmethod
  def report_key(cls):
    return "donations_report"

  @classmethod
  def report_uri(cls):
    return secret("donations_event_url")
  
  @classmethod
  def report_data(cls):
    return {
    	"__EVENTTARGET": "ctl00$save_button",
    	"ctl00$fund_dropdown": "12777",
	    "ctl00$start_date": "07/21/2024",
    	"ctl00$finish_date": "07/20/2025"
    }
  
  {
}
  
  @classmethod
  def google_drive_name(cls):
    return "donations_report.csv"
  
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
    translated_rows = [{field: self.translate_value(field, row[index_map[field]]) for field in index_map.keys()} for row in raw_rows]
    
    return translated_rows
  
  def translate_value(self, field, raw_value):
    if "phone" in field or field == "zip":
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
      "fund_name": "fund_name",
      "fund_active": "fund_active",
      "fund_allows_anonymous": "fund_allows_anonymous",
      "aga_id": "member_number",
      "full_name": "full_name",
      "salutation": "salutation",
      "name_given": "first_name",
      "name_family": "last_name",
      "is_member": "is_member",
      "address1": "address1",
      "address2": "address2",
      "city": "city",
      "state": "state",
      "postcode": "zip",
      "country": "country",
      "phone_cell": "phone",
      "email": "primary_email",
      "donation_date": "donation_date",
      "earliest_date_exported": "earliest_date_exported",
      "donation_amount": "donation_amount",
      "payment_status": "payment_status",
      "transrefnum": "reference_number",
      "donation_comment": "donation_comment",
      "anonymous": "anonymous",
      "name_on_donation_record": "name_on_donation_record",
      "donation_type": "donation_type",
      "donation_honoree_name": "donation_honoree_name",
      "send_someone_notification": "send_someone_notification",
      "notification_to_name": "notification_to_name",
      "notification_to_address1": "notification_to_address1",
      "notification_to_address2": "notification_to_address2",
      "notification_to_city": "notification_to_city",
      "notification_to_state": "notification_to_state",
      "notification_to_zip": "notification_to_zip",
      "notification_to_country": "notification_to_country",
      "notification_to_email": "notification_to_email",
      "employer_matches": "employer_matches",
      "donor_will_mail_form": "donor_will_mail_form",
      "matching_employer_name": "matching_employer_name",
      "matching_employer_city": "matching_employer_city",
      "matching_employer_state": "matching_employer_state",
      "matching_employer_contact_person": "matching_employer_contact_person",
      "matching_employer_contact_phone": "matching_employer_contact_phone",
      "employer_matching_terms": "employer_matching_terms",
      "matching_donation_paid_amount": "matching_donation_paid_amount",
      "matching_donation_paid_date": "matching_donation_paid_date",
      "learn_about_other_opportunities": "learn_about_other_opportunities",
      "learn_about_will_and_estate_plans": "learn_about_will_and_estate_plans",
    }
