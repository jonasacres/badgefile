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

  def read_manual_badge_data(self):
    file_id = self.locate_file()
    data = read_sheet_data(self.service, file_id, "Manual Badges")
    row_map = [ 'badgefile_id', 'description', 'name_given', 'name_family', 'city', 'state', 'country', 'badge_rating', 'title',  'email', 'phone', 'badge_type', 'speaks_english', 'speaks_chinese', 'speaks_korean', 'speaks_japanese', 'speaks_spanish']
    
    result = []
    for row in data[1:]:
      row_dict = {}
      for i, key in enumerate(row_map):
        if i < len(row):
          row_dict[key] = row[i]
        else:
          row_dict[key] = None
      result.append(row_dict)
    return result

  def read_tournament_overrides(self):    
    file_id = self.locate_file()
    data = read_sheet_data(self.service, file_id, "Tournaments")

    if data is None or len(data) == 0:
      log.info("Unable to read tournament overrides; Tournaments sheet is missing or empty")
      return None
    
    # Find indices for key columns
    # "why did you write it so dumb" because i only cared about agaid and override_rating at the time...
    indices = {}
    keys = {
      "AGAID": "agaid",
      "Override Rating (Editable)": "override_rating",
      "Ignore Problems (Editable)": "ignore_problems",
      "Final Open": "final_open",
      "Final Womens": "final_womens",
      "Final Seniors": "final_seniors",
      "Final Diehard": "final_diehard",
    }
    
    
    for idx, column_title in enumerate(data[0]):
      if column_title in keys:
        indices[keys[column_title]] = idx
    for title, key in keys.items():
      if not key in indices:
        log.error(f"Unable to read tournament overrides; can't find expected column for {key} (expect column header '{title}')")
        return None

    for row_idx, row in enumerate(data[1:]):
      try:
        agaid = int(row[indices['agaid']]) if indices['agaid'] < len(row) else None
        override_rating = row[indices['override_rating']] if indices['override_rating'] < len(row) else None
        ignore_problems = row[indices['agaid']].lower() if indices['ignore_problems'] < len(row) else None

        if agaid is None:
          continue

        attendee = self.badgefile.lookup_attendee(agaid)
        if attendee is None:
          log.warn(f"Tournaments row {row_idx+1} has non-existent attendee {indices['agaid']}")
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
        
        bool_truthy_values = ("1", "true", "yes", "ok")
        attendee.set_ignore_tournament_issues(ignore_problems in bool_truthy_values)
        for key in ['open', 'womens', 'seniors', 'diehard']:
          index = indices['final_'+key]
          if len(row) > index:
            if key == 'open':
              log.info(f"Attendee {attendee.full_name()} {attendee.id()} has final_{key}='{row[index]}', idx={index}")
            in_tournament = row[index].lower() in bool_truthy_values
            attendee.set_in_tournament(key, in_tournament)
          else:
            log.warn(f"Attendee {attendee.full_name()} {attendee.id()} does not have final_{key} column (lol what the fuck ever)")

      except Exception as exc:
        log.warn(f"Caught exception processing row {row_idx+1} of Tournaments", exception=exc)
