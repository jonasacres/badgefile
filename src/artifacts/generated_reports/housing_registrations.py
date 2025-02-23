import os
import csv
import json
from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class HousingRegistrationsReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def housing_registration_row(self, attendee):
    info = attendee.info()
    housing = attendee.party_housing()
    meals = attendee.party_meal_plan()

    num_beds = sum(booking.num_beds() for booking in housing if booking.num_beds() is not None)
    problems = " | ".join([issue['msg'] for issue in attendee.issues_in_category('housing')])
    
    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      attendee.age_at_congress(),
      info['country'],
      housing[0].regtime(),
      info['email'],
      attendee.phone(),
      len(attendee.party()),
      meals.num_meal_plans() if meals else 0,
      num_beds,
      sum([booking.num_units() for booking in housing if booking.is_dorm_double()]),
      sum([booking.num_units() for booking in housing if booking.is_dorm_single()]),
      sum([booking.num_units() for booking in housing if booking.is_apt1_1room()]),
      sum([booking.num_units() for booking in housing if booking.is_apt1_2room()]),
      sum([booking.num_units() for booking in housing if booking.is_apt2_1room()]),
      sum([booking.num_units() for booking in housing if booking.is_apt2_2room()]),
      problems,
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGAID",
      "Age at Congress",
      "Country of Origin",
      "Housing Reg. Date",
      "Email",
      "Phone",
      "Party Size",
      "# Meal Plans",
      "Total Beds Booked",
      "# Dorm Double",
      "# Dorm Single",
      "# Apt 1 (Half)",
      "# Apt 1 (Whole)",
      "# Apt 2 (Half)",
      "# Apt 2 (Whole)",
      "Problems?",
      "Approved?",
      "Registrar Comments",
    ]
    
    sheet_data = [self.housing_registration_row(att) for att in self.badgefile.attendees() if att.is_primary() and len(att.party_housing()) > 0]
    service = authenticate_service_account()
    
    log.debug("housing_registration_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Housing Registration", secret("folder_id"))


