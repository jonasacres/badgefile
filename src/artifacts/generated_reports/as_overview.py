import os
import csv
from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class OverviewReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def status_row(self, attendee):
    issue_categories = attendee.issue_categories()
    housing_ok    = 'housing'    not in issue_categories
    youth_ok      = 'youthform'  not in issue_categories
    tournament_ok = 'tournament' not in issue_categories
    membership_ok = 'membership' not in issue_categories
    payment_ok    = 'payment'    not in issue_categories
    
    # Check for any issues in categories not already checked
    known_categories = {'housing', 'youthform', 'tournament', 'membership', 'payment'}
    other_issues_ok = not any(cat not in known_categories for cat in issue_categories)
    all_good = housing_ok and youth_ok and tournament_ok and membership_ok and payment_ok

    info = attendee.info()
    primary = attendee.primary()
    pri_info = attendee.primary().info()

    if attendee.party_housing() is None or len(attendee.party_housing()) == 0:
      if attendee.will_arrange_own_housing():
        housing_status = "SELF"
      else:
        housing_status = "NONE"
    else:
      housing_status = "OK" if housing_ok else "PENDING"

    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      attendee.age_at_congress(),
      info['country'],
      "YES" if attendee.is_primary() else "NO",
      primary.id(),
      
      f"{pri_info['name_family']}, {pri_info['name_given']} {pri_info['name_mi'] if pri_info['name_mi'] else ''}",
      pri_info['email'],
      primary.phone(),
      info['regtype'],
      info['regtime'],

      "OK" if all_good        else "PENDING",
      housing_status,
      "OK" if youth_ok        else "PENDING",
      "OK" if tournament_ok   else "PENDING",
      "OK" if membership_ok   else "PENDING",
      "OK" if payment_ok      else "PENDING",
      "OK" if other_issues_ok else "PENDING",
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGAID",
      "Age at Congress",
      "Country of Origin",
      "Is Primary?",
      "Primary Reg. ID",
      "Primary Reg. Name",
      "Primary Reg. Email",
      "Primary Reg. Phone",
      "Reg. Type",
      "Reg. Date",
      "All good?",
      "Housing?",
      "Youth form?",
      "Tournaments?",
      "Membership?",
      "Paid?",
      "Other issues?",
      "Comments (Editable)",
    ]
    
    sheet_data = [self.status_row(att) for att in self.badgefile.attendees()]
    service = authenticate_service_account()
    
    log.debug("master_status_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Overview", secret("folder_id"))


