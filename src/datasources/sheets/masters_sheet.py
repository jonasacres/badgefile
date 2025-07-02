from datetime import datetime
from util.secrets import secret
from integrations.google_api import read_sheet_data, authenticate_service_account
from log.logger import log

class MastersSheet:
  def __init__(self, badgefile):
    self.badgefile = badgefile

  def read_sheet(self):
    log.info(f"Reading Masters sheet...")
    self.assignments = {}
    service = authenticate_service_account()
    file_id = secret("masters_sheet_file_id")
    data = read_sheet_data(service, file_id, sheet_name="Masters Players")
    masters = []

    for row in data:
      try:
        if len(row) <= 3:
          continue
        agaid = int(row[3])
        masters.append(agaid)
      except ValueError:
        continue
    
    for attendee in self.badgefile.attendees():
      in_masters = attendee.id() in masters
      print(f"Player {attendee.id()} {attendee.full_name()} -- {in_masters}")
      attendee.set_in_masters(in_masters)
