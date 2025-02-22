import os
import csv
from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class HousingRegistrationsReport:
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

  def housing_registration_row(self, activity):
    attendee = activity.attendee
    info = attendee.info()
    act_info = activity.info()

    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      act_info["activity_title"],
      activity.roommate_request(),
      activity.roommate_request_comments(),
    ]

  def update(self):
    sheet_header = [
      "Name",
      "Pri. Reg. AGAID",
      "Room Type",
      "Roommate Request",
      "Roommate Request Comments",
      "Occupant ID",
      "Occupant Name",
      "Virtual Room #",
      "Physical Room #",
    ]
    
    sheet_data = [self.housing_registration_row(att) for att in self.badgefile.attendees() if att.is_primary() and len(att.party_housing()) > 0]
    service = authenticate_service_account()
    
    log.debug("housing_registration_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Housing Assignments", secret("folder_id"))


