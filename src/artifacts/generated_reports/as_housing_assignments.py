import os
import csv
from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class HousingAssignmentsReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def format_room_type(self, activity):
    if activity.is_apt1_1room():
      return "apt1-1room"
    elif activity.is_apt1_2room():
      return "apt1-2room"
    elif activity.is_apt2_1room():
      return "apt2-1room"
    elif activity.is_apt2_2room():
      return "apt2-2room"
    elif activity.is_dorm_single():
      return "dorm-single"
    elif activity.is_dorm_double():
      return "dorm-double"
    else:
      return activity.info()["activity_title"]

  def housing_registration_row(self, unit):
    activity = unit["activity"]
    unit_id = unit["id"]
    attendee = activity.attendee
    info = attendee.info()
    act_info = activity.info()

    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      unit_id,
      attendee.id(),
      activity.regtime(),
      self.format_room_type(activity),
      activity.num_beds() / activity.num_units(),
      activity.roommate_request(),
      activity.roommate_request_comments(),
    ]

  def update(self):
    sheet_header = [
      "Name",
      "Housing unit ID",
      "Pri. Reg. AGAID",
      "Booking Time",
      "Room Type",
      "Num. Beds",
      "Roommate Request",
      "Roommate Request Comments",
      "Occupant ID",
      "Occupant Name",
      "Virtual Room #",
      "Physical Room #",
    ]
    
    housing_activities = []
    seen_ids = set()
    
    # activity_registrant_id is a unique ID for each line item in the housing registration, NOT the attendee ID
    for attendee in self.badgefile.attendees():
      for activity in attendee.activities():
        if activity.is_housing() and activity.is_open() and activity.info()["activity_registrant_id"] not in seen_ids:
          housing_activities.append(activity)
          seen_ids.add(activity.info()["activity_registrant_id"])

    housing_activities.sort(key=lambda activity: activity.info()["activity_registrant_id"])
    housing_units = []

    # if activity.num_units() > 1, then we need to add a row for each unit
    for activity in housing_activities:
      for i in range(int(activity.num_units() + 0.5)):
        housing_units.append({"activity": activity, "id":f"{activity.info()['activity_registrant_id']}-{i}"})
    
    sheet_data = [self.housing_registration_row(unit) for unit in housing_units]
    service = authenticate_service_account()

    log.debug("housing_assignments: Updating")
    # Only update the first 8 columns (our actual data), preserve any columns after that
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Housing Assignments", secret("folder_id"), valueInputOption='USER_ENTERED', preserve_columns_after=8)


