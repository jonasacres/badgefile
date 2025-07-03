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

    header = data[0]
    
    confirmed_idx = None
    agaid_idx = None

    for i, col in enumerate(header):
      if col == "Confirmed?":
        confirmed_idx = i
      elif col == "AGA ID":
        agaid_idx = i
    
    max_idx = max(confirmed_idx, agaid_idx)
    if agaid_idx is None:
      log.error("AGA ID column not found in Masters sheet")
      return
    
    if confirmed_idx is None:
      log.error("Confirmed? column not found in Masters sheet")
      return

    for row in data:
      try:
        if len(row) <= max_idx:
          continue
        agaid = int(row[agaid_idx])
        if row[confirmed_idx].lower() == "y":
          log.debug(f"Adding {agaid} to Masters")
          masters.append(agaid)
        else:
          log.debug(f"Not adding {agaid} to Masters because player is not confirmed")
      except ValueError:
        continue
    
    for attendee in self.badgefile.attendees():
      in_masters = attendee.id() in masters
      attendee.set_in_tournament('masters', in_masters)
