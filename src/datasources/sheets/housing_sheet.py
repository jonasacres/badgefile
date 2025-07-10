from datetime import datetime
from util.secrets import secret
from integrations.google_api import read_sheet_data, authenticate_service_account
from log.logger import log

class HousingSheet:
  def __init__(self, badgefile):
    self.badgefile = badgefile

  def read_sheet(self):
    log.info(f"Reading housing sheet...")
    self.assignments = {}
    service = authenticate_service_account()
    file_id = secret("housing_sheet_file_id")
    badge_tabs = {
      "Moody Shearn Res Hall": "Moody Shearn",
      "Herman Brown Res Hall": "Herman Brown",
      "Dorothy Lord Center Apt": "Dorothy Lord Center",
      "Lord Center Apt - Keys": "Lord Center",
    }

    for tab, building_name in badge_tabs.items():
      data = read_sheet_data(service, file_id, sheet_name=tab)
      map = self.housing_column_map()
      dorm_assignments = [self.transform_row({map[i]: val for i, val in enumerate(row)}) for row in data if self.housing_row_looks_legit(row)]
      for assignment in dorm_assignments:
        assignment['building'] = building_name
        attendees = self.locate_attendees_for_assignment(assignment, tab)
        for attendee in attendees:
          if attendee.id() in self.assignments:
            existing = self.assignments[attendee.id()]
            log.notice(f"Attendee {attendee.id()} {attendee.full_name()} has multiple assignments in housing (e.g. {assignment['building']} {assignment['room_assigned']} and {existing['building']} {existing['room_assigned']})")
          else:
            self.assignments[attendee.id()] = assignment
    
    meal_tab = "Meal Plans ONLY"
    meal_data = read_sheet_data(service, file_id, sheet_name=meal_tab)
    map = self.meal_column_map()
    meal_assignments = [self.transform_row({map[i]: val for i, val in enumerate(row)}) for row in meal_data if self.meal_row_looks_legit(row)]
    for assignment in meal_assignments:
      attendees = self.locate_attendees_for_assignment(assignment, meal_tab)
      for attendee in attendees:
        if attendee.id() in self.assignments:
          existing = self.assignments[attendee.id()]
          log.notice(f"Attendee {attendee.id()} {attendee.full_name()} has multiple assignments including meal plan-only row")
        else:
          self.assignments[attendee.id()] = assignment

    for attendee_id, assignment in self.assignments.items():
      attendee = self.badgefile.lookup_attendee(attendee_id)
      attendee.set_housing_assignment(assignment)

    log.debug(f"{len(self.assignments)} attendees have housing/meal assignments")
  
  def housing_row_looks_legit(self, row):
    necessary_cols = [1, 2]
    for idx in necessary_cols:
      if len(row) <= idx or row[idx] == None or len(row[idx]) == 0:
        return False
    try:
      int(row[1])
    except ValueError:
      return False
    return True
  
  def meal_row_looks_legit(self, row):
    necessary_cols = [1, 2]
    for idx in necessary_cols:
      if len(row) <= idx or row[idx] == None or len(row[idx]) == 0:
        return False
    if not row[2] in ['TRUE', 'FALSE']:
      return False
    return True
  
  def locate_attendees_for_assignment(self, response, tab):
    manual = self.locate_manually_mapped_attendees(response, tab)
    if manual:
      return manual
    
    name_stripped = response['name_assigned'].lower().strip()

    for attendee in self.badgefile.attendees():
      ai = attendee.info()
      given = (ai.get("name_given", "") or "").strip()
      family = (ai.get("name_family", "") or "").strip()
      mi = (ai.get("name_mi", "") or "").strip()

      name_renderings = [
        f"{given} {family}".lower(),
        f"{family} {given}".lower(),
        f"{given} {mi} {family}".lower(),
        f"{family} {mi} {given}".lower(),
        f"{family}, {given}".lower(),
        f"{family}, {given} {mi}".lower(),
        f"{given}, {family}".lower(),
        f"{given}, {family} {mi}".lower(),
      ]
      if name_stripped in name_renderings:
        return [attendee]
    
    log.notice(f"Cannot find matching registration for housing/meal assignment with name '{response['name_assigned']}', tab {tab}, card {response['card_number']}'")
    return []
  
  def locate_manually_mapped_attendees(self, response, tab):
    import yaml
    import os

    # Try to load the housing_name_maps.yaml file only once and cache it
    if not hasattr(self, "_housing_name_map"):
      housing_name_map_path = "housing_name_maps.yaml"
      if os.path.exists(housing_name_map_path):
        with open(housing_name_map_path, "r", encoding="utf-8") as f:
          self._housing_name_map = yaml.safe_load(f)
      else:
        self._housing_name_map = {}
      
      print(self._housing_name_map)

    # Check if the assigned name is in the map
    name_map = self._housing_name_map
    if response['name_assigned'] in name_map:
      badgefile_ids = name_map[response['name_assigned']]
      if isinstance(badgefile_ids, int):
        badgefile_ids = [badgefile_ids]
      elif not isinstance(badgefile_ids, list):
        badgefile_ids = [badgefile_ids]
      attendees = []
      for bid in badgefile_ids:
        attendee = self.badgefile.lookup_attendee(bid)
        if attendee is not None:
          attendees.append(attendee)
      if attendees:
        return attendees
  
  def transform_row(self, row):
    transformed = row.copy()
    bool_cols = ['friday_arrival', 'meal_plan', 'badge_received', 'badge_returned']
    for col in bool_cols:
      if col in row:
        if row[col] == 'TRUE':
          transformed[col] = True
        elif row[col] == 'FALSE':
          transformed[col] = False
        else:
          log.warn(f"Unrecognized value {col}='{row[col]}' in row for card #{row['card_number']}, {row['name_assigned']}")
    for col, value in transformed.items():
      if isinstance(value, str):
        transformed[col] = value.encode('latin-1').decode('utf-8')
    return transformed
    
  def housing_column_map(self):
    return [
      'card_number',
      'room_assigned',
      'name_assigned',
      'friday_arrival',
      'meal_plan',
      'badge_returned',
      'badge_received',
      'notes'
    ]

  def meal_column_map(self):
    return [
      'card_number',
      'name_assigned',
      'meal_plan',
      'notes'
    ]