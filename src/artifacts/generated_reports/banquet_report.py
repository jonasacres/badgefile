import csv
import os
from log.logger import log
from integrations.google_api import authenticate_service_account, upload_csv_to_drive
from util.secrets import secret

class BanquetReport:
  """Provides a list of donors by badgefile ID and tier level."""

  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def generate(self, path):
    log.info(f"banquet_report: generating banquet report at {path}")
    def header_row():
      return ['badgefile_id', 'name_given', 'name_family', 'age_at_congress']
    
    eligible = [attendee for attendee in self.badgefile.attendees() if attendee.is_attending_banquet()]
    results = [{key: attendee.final_info()[key] for key in header_row()} for attendee in eligible]

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.DictWriter(file, fieldnames=header_row())
      writer.writerow({key:key for key in header_row()})
      writer.writerows(results)

    log.debug(f"banquet_report: Generation complete, {len(results)} banquet attendees.")
    self.upload(path)

  def upload(self, path):
    log.debug(f"banquet_report: Uploading to Google Drive.")
    folder_id = secret("folder_id")
    service = authenticate_service_account()
    upload_csv_to_drive(service, path, "banquet_report.csv", folder_id)
    log.debug(f"banquet_report: Upload complete.")

