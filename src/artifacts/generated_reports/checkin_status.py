import csv
import os
from log.logger import log
from integrations.google_api import authenticate_service_account, upload_csv_to_drive
from util.secrets import secret

class CheckinStatusReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile

  def render_row(self, attendee):
    info = attendee.info()
    pri = attendee.primary().info()

    return [
      info['badgefile_id'],
      info['name_given'],
      info['name_family'],
      pri['badgefile_id'],
      pri['name_given'] + ' ' + pri['name_family'],
      attendee.is_checked_in(),
    ]
  
  def generate(self, path):
    log.info(f"checkin_status_report: generating check-in report at {path}")
    def header_row():
      return ['AGA # / BFID',
              'First Name',
              'Last Name',
              'Primary Registrant ID',
              'Pri. Name',
              'Checked In?',
]
    
    results = [self.render_row(attendee) for attendee in self.badgefile.attendees()]

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.writer(file)
      writer.writerow(header_row())
      writer.writerows(results)

    log.debug(f"checkin_status_report: Generation complete, {len(results)} attendees.")
    self.upload(path)

  def upload(self, path):
    log.debug(f"checkin_status_report: Uploading to Google Drive.")
    folder_id = secret("folder_id")
    service = authenticate_service_account()
    upload_csv_to_drive(service, path, "checkin_status_report.csv", folder_id)
    log.debug(f"checkin_status_report: Upload complete.")

