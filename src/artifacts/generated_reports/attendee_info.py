import csv
import os
from log.logger import log
from integrations.google_api import authenticate_service_account, upload_csv_to_drive
from util.secrets import secret

class AttendeeInfo:
  """Provides a list of Congress attendees."""

  def __init__(self, badgefile):
    self.badgefile = badgefile

  def prepare_row(self, attendee):
    info = attendee.info().copy()
    
    if info.get('donation_is_anonymous', True):
      info['donation_tier'] = 'nondonor'
    info['staying_on_campus'] = len(attendee.party_housing()) > 0

    tournaments = attendee.tournaments()
    info['in_masters'] = 'masters' in tournaments
    info['in_open'] = 'open' in tournaments
    info['in_diehard'] = 'diehard' in tournaments
    info['in_seniors'] = 'seniors' in tournaments
    info['in_womens'] = 'womens' in tournaments
    info['languages'] = ', '.join(attendee.languages())

    return info

  
  def generate(self, path):
    log.info(f"attendee_info: generating attendee info report at {path}")
    def header_row():
      return [
        'badgefile_id',
        'name_given',
        'name_family',
        'name_mi',
        'email',
        'title',
        'badge_rating',
        'donation_tier',
        'staying_on_campus',
        'in_masters',
        'in_open',
        'in_diehard',
        'in_seniors',
        'in_womens',
        'languages',
        'city',
        'state',
        'country',
        'aga_rating',
        'aga_chapter',
        'member_type',
      ]
        
    results = [{key: self.prepare_row(attendee).get(key, None) for key in header_row()} for attendee in self.badgefile.attendees()]

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8') as file:
      writer = csv.DictWriter(file, fieldnames=header_row())
      writer.writerow({key:key for key in header_row()})
      writer.writerows(results)

    log.debug(f"attendee_info: Generation complete, {len(results)} attendees.")
    self.upload(path)

  def upload(self, path):
    log.debug(f"attendee_info: Uploading to Google Drive.")
    folder_id = secret("folder_id")
    service = authenticate_service_account()
    upload_csv_to_drive(service, path, "attendee_info.csv", folder_id)
    log.debug(f"attendee_info: Upload complete.")

