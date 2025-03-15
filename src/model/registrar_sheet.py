from util.secrets import secret
from log.logger import log
from integrations.google_api import authenticate_service_account, locate_existing_files, read_sheet_data

class RegistrarSheet:
  def __init__(self, badgefile, folder_id=None, file_name="Attendee Status"):
    self.badgefile = badgefile
    self.folder_id = folder_id or secret("folder_id")
    self.file_name = file_name

  def _download_tab(self, sheet_name):
    service = authenticate_service_account()
    files = locate_existing_files(service, self.file_name, self.folder_id)
    
    if len(files) == 0:
      log.warn(f"No attendee status report named '{self.file_name}' in folder {self.folder_id}")
      return []
    
    file_id = files[0]['id']
    if len(files) > 1:
      log.warn(f"Multiple attendee status reports named '{self.file_name}' in folder {self.folder_id}; found {len(files)}, picking {file_id}")
    
    log.debug(f"Reading {file_id} to obtain {self.file_name}, tab {sheet_name}")
    data = read_sheet_data(service, file_id, sheet_name)
    return data

  def update_from_housing_registration(self):
    log.info("Pulling approval information from Housing Registration tab")
    data = self._download_tab("Housing Registration")
    log.debug(f"Housing Registration tab has {len(data)} rows (including header)")
    
    for row in data:
      # Skip header row by checking if second column is numeric
      try:
        int(row[1])
      except (ValueError, IndexError):
        continue
      
      badgefile_id = int(row[1])
      attendee = self.badgefile.lookup_attendee(badgefile_id)
      if attendee == None:
        log.warn(f"Unable locate attendee with badgefile ID {badgefile_id} ({row[0]}), as listed in Housing Registration tab")
        continue
      
      # Get approval field (column R)
      approval = row[17] if len(row) > 17 else None
      if approval == None or approval.strip() == "":
        attendee.set_housing_approval(False)
        continue

      if approval.lower() != "yes":
        # a registrar team member might have entered something in wrong; don't take any action, but record the issue conspicuously
        log.warn(f"Housing registration for {attendee.id()} ({attendee.full_name()}) has non-Yes approval status: {approval}")
        continue
      
      # Update attendee's housing approval status
      attendee.set_housing_approval(True)
    
