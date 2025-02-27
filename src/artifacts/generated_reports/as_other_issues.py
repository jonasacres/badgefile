import os
import csv
import json
from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class OtherIssuesReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def issue_row(self, attendee, issue):
    info = attendee.info()

    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      "YES" if attendee.is_primary() else "NO",
      attendee.age_at_congress(),
      info['email'],
      attendee.primary().info()['email'],
      issue['category'],
      issue['code'],
      issue['msg'],
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGA ID",
      "Is primary?",
      "Age at Congress",
      "Contact e-mail",
      "Pri. contact e-mail",
      "Issue Category",
      "Issue Code",
      "Issue Description",
      "Ignore?",
      "Comments",
    ]
    
    attendee_issues = []
    ignored_categories = [ "housing", "youthform", "tournament", "membership", "payment" ]
    
    for attendee in self.badgefile.attendees():
      for issue_json in attendee.open_issues().values():
        issue = json.loads(issue_json)
        if issue['category'] not in ignored_categories:
          attendee_issues.append([attendee, issue])

    sheet_data = [self.issue_row(attiss[0], attiss[1]) for attiss in attendee_issues]
    service = authenticate_service_account()
    
    log.debug("other_issues: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Other Issues", secret("folder_id"))


