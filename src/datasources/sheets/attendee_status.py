from util.secrets import secret
from integrations.google_api import read_sheet_data, authenticate_service_account, locate_existing_files
from log.logger import log

class AttendeeStatusSource:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    self.file_name = "Attendee Status"
    self.folder_id = secret("folder_id")
    self.service = authenticate_service_account()
    self.file_id = None

  def locate_file(self):
    if self.file_id is None:
      files = locate_existing_files(self.service, self.file_name, self.folder_id)

      if len(files) == 0:
        log.info(f"Unable to locate {self.file_name} in folder {self.folder_id}")
        return None
      
      self.file_id = files[0]['id']
    return self.file_id

  def read_tournament_overrides(self):    
    file_id = self.locate_file()
    data = read_sheet_data(self.service, file_id, "Tournaments")

    if data is None or len(data) == 0:
      log.info("Unable to read tournament overrides; Tournaments sheet is missing or empty")
      return None
    
    # Find indices for key columns
    agaid_idx = -1
    override_rating_idx = -1
    ignore_problems_idx = -1
    
    for idx, column_title in enumerate(data[0]):
      if column_title and isinstance(column_title, str):
        title_lower = column_title.lower()
        if "agaid" in title_lower:
          agaid_idx = idx
        elif "override rating" in title_lower:
          override_rating_idx = idx
        elif "ignore problems" in title_lower:
          ignore_problems_idx = idx
    
    if agaid_idx == -1 or override_rating_idx == -1 or ignore_problems_idx == -1:
      log.info("Unable to read tournament overrides; can't find required columns")
      return None

    for row_idx, row in enumerate(data[1:]):
      try:
        agaid = int(row[agaid_idx]) if agaid_idx < len(row) else None
        override_rating = row[override_rating_idx] if override_rating_idx < len(row) else None
        ignore_problems = row[agaid_idx].lower() if ignore_problems_idx < len(row) else None

        if agaid is None:
          continue

        attendee = self.badgefile.lookup_attendee(agaid)
        if attendee is None:
          log.warn(f"Tournaments row {row_idx+1} has non-existent attendee {agaid_idx}")
          continue
        
        # Process override_rating
        if override_rating == "" or (isinstance(override_rating, str) and override_rating.strip() == ""):
          override_rating = None
        if override_rating:
          try:
            # Try to convert to float
            override_rating = float(override_rating)
          except (ValueError, TypeError):
            if override_rating.strip().lower() != "aga":
              log.warn(f"Invalid override rating '{override_rating}' for attendee {agaid} in row {row_idx+1}")
            override_rating = None
        
        # setting override_rating None will clear the override
        attendee.override_rating(override_rating)
        
        ignore_problems_bool = ignore_problems in ("1", "true", "yes", "ok")
        attendee.set_ignore_tournament_issues(ignore_problems_bool)

      except Exception as exc:
        log.warn(f"Caught exception processing row {row_idx+1} of Tournaments", exception=exc)
