import csv
import os
from log.logger import *
from ..google.google_drive import authenticate_service_account, upload_csv_to_drive
from util.secrets import secret

class DonorReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def generate(self, path):
    log_info(f"donor_report: generating donor report at {path}")
    def header_row():
      return ['badgefile_id', 'donation_tier', 'donation_name', 'donation_is_anonymous']
        
    results = [{key: attendee.info()[key] for key in header_row()} for attendee in self.badgefile.attendees()]
    results = [result for result in results if result['donation_tier'] != 'nondonor']

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.DictWriter(file, fieldnames=header_row())
      writer.writerow({key:key for key in header_row()})
      writer.writerows(results)

    log_debug(f"donor_report: Generation complete, {len(results)} attendees.")
    self.upload(path)

  def upload(self, path):
    log_debug(f"donor_report: Uploading to Google Drive.")
    folder_id = secret("folder_id")
    service = authenticate_service_account()
    upload_csv_to_drive(service, path, "donor_report.csv", folder_id)
    log_debug(f"donor_report: Upload complete.")

