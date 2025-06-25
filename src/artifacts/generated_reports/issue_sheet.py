import json
import csv
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from integrations.google_api import authenticate_service_account, upload_csv_to_drive
from util.secrets import secret

class IssueSheet:
  """Provides a list of each individual outstanding issue for all Congress attendees."""
  
  def __init__(self, badgefile):
    self.badgefile = badgefile

  def generate(self, path):
    has_issues = [att for att in self.badgefile.attendees() if len(att.open_issues()) > 0 and not att.is_cancelled()]
    issues = []

    for attendee in has_issues:
      info = attendee.info()
      pri = attendee.primary()
      pri_info = pri.info()

      rt_lower = info['regtype'].lower()
      is_primary = "you -" in rt_lower
      is_youth = "- youth" in rt_lower
      is_participant = "non-participant" not in rt_lower

      adult_line = ""
      if is_participant:
        adult_line = "Youth" if is_youth else "Adult"
      else:
        adult_line = ""
      
      attendee_preamble = [
        info['badgefile_id'],
        "Primary" if is_primary else "Non-primary",
        adult_line,
        "Player" if is_participant else "Non-participant",
        info['name_family'],
        info['name_given'],
        info['country'],
        info['languages'],
        info['date_of_birth'],
        attendee.age_at_congress(),
        info['email'],
        attendee.phone(),
      ]
        
      primary_preamble = [
        f"{pri_info['name_family']}, {pri_info['name_given']} #{pri_info['badgefile_id']}",
        pri_info['email'],
        pri.phone(),
      ]

      transaction_preamble = [
        info['transrefnum'],
      ]

      preamble = attendee_preamble + primary_preamble + transaction_preamble

      for issue_type, issue_data in attendee.open_issues().items():
        parsed = json.loads(issue_data)
        issues.append(preamble + [issue_type, parsed['code'], parsed['msg']])
    
    # Sort issues by [(primary last name, primary first name), name_family, name_given, date_of_birth, issue_type]
    issues.sort(key=lambda x: (str(x[12]), str(x[4]), str(x[8]), str(x[16])))

    # Write issues to CSV at the specified path
    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.writer(file)
      
      # Write header row
      writer.writerow([
        "Badgefile ID",
        "Primary?",
        "Adult?",
        "Player?",
        "Last Name",
        "First Name",
        "Country",
        "Languages",
        "Date of Birth",
        "Age at Congress",
        "Email",
        "Phone",
        "Primary Registrant",
        "Primary Email",
        "Primary Phone",
        "Trans Ref Num",
        "Issue Type",
        "Issue Code",
        "Issue Description"
      ])

      # Write each issue as a row
      writer.writerows(issues)
    
    self.upload(path)
  
  def upload(self, path):
    folder_id = secret("folder_id")
    service = authenticate_service_account()
    upload_csv_to_drive(service, path, "issue_data.csv", folder_id)