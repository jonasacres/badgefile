from datetime import datetime
from integrations.google_api import update_sheets_worksheet, create_sheet_if_not_exists, authenticate_service_account
from model.email_history import EmailHistory
from util.secrets import secret

from log.logger import log

class AggregateReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile

  
  def make_registration_row(self, title, population):
    base_row = self.make_standard_row(title, population)
    primaries = [att for att in population if att.is_primary()]
    party_size_counts = [
      len([att for att in primaries if len(att.party()) == 1]),
      len([att for att in primaries if len(att.party()) == 2]), 
      len([att for att in primaries if len(att.party()) == 3]),
      len([att for att in primaries if len(att.party()) == 4]),
      len([att for att in primaries if len(att.party()) >= 5])
    ]

    return base_row + [""] + party_size_counts

  def make_standard_row(self, title, population):
    return [
      title,
      len(population),
      len([att for att in population if att.age_at_congress() < 18]),
      len([att for att in population if att.age_at_congress() >= 18 and att.age_at_congress() < 23]),
      len([att for att in population if att.age_at_congress() >= 23]),
    ]
  
  def make_heading_row(self, row):
    return row
  
  def make_simple_row(self, title, count):
    return [
      title,
      count,
    ]
  
  def render_row(self, row):
    if len(row) == 0:
      return []
    if not any(isinstance(x, list) for x in row):
      return self.make_heading_row(row)
    if row[0] == "Registration":
      return self.make_registration_row(row[0], row[1])
    if isinstance(row[1], list):
      return self.make_standard_row(row[0], row[1])
    return self.make_simple_row(row[0], row[1])

  def update(self):
    all_attendees = self.badgefile.attendees()
    real_attendees = [att for att in all_attendees if not att.is_cancelled()]
    primaries = [att for att in real_attendees if att.is_primary()]
    translators = [att for att in real_attendees if att.info().get('translator', '') == "Yes"]
    housing = []
    
    for pri in primaries:
      for housing_item in pri.party_housing():
        housing.append(housing_item)

    num_dorm_beds_booked = sum([item.num_units() for item in housing if item.is_dorm_double()]) + 2*sum([item.num_units() for item in housing if item.is_dorm_single()])
    num_apt1_beds_booked = sum([item.num_units() for item in housing if item.is_apt1_1room()]) + 2*sum([item.num_units() for item in housing if item.is_apt1_2room()])
    num_apt2_beds_booked = sum([item.num_units() for item in housing if item.is_apt2_1room()]) + 2*sum([item.num_units() for item in housing if item.is_apt2_2room()])
    num_vip_beds_booked = 0

    row_defs = [
      ["Registration", real_attendees],
      ["Participants", [att for att in real_attendees if att.is_participant()]],
      ["Non-Participants", [att for att in real_attendees if not att.is_participant()]],
      ["Full Week", [att for att in real_attendees if att.is_full_week()]],
      ["Partial Week", [att for att in real_attendees if att.is_partial_week()]],
      ["Cancellations", [att for att in all_attendees if att.is_cancelled()]],
      [],
      ["Precheck Status"],
      ["Attendees with No Issues", [att for att in real_attendees if len(att.open_issues()) == 0]],
      ["Attendees with Any Issues", [att for att in real_attendees if len(att.open_issues()) > 0]],
      ["Attendees with Housing Issues", [att for att in real_attendees if len(att.issues_in_category("housing")) > 0]],
      ["Attendees with Youth Form Issues", [att for att in real_attendees if len(att.issues_in_category("youthform")) > 0]],
      ["Attendees with Tournament Issues", [att for att in real_attendees if len(att.issues_in_category("tournament")) > 0]],
      ["Attendees with Membership Issues", [att for att in real_attendees if len(att.issues_in_category("membership")) > 0]],
      ["Attendees with Payment Issues", [att for att in real_attendees if len(att.issues_in_category("payment")) > 0]],
      ["Attendees with Other Issues", [att for att in real_attendees if any(cat not in ["housing", "youthform", "tournament", "membership", "payment"] for cat in att.issue_categories())]],
      [],
      ["Tournament Enrollment"],
      ["Masters", [att for att in real_attendees if "masters" in att.tournaments()]],
      ["US Open", [att for att in real_attendees if "open" in att.tournaments()]],
      ["Womens", [att for att in real_attendees if "womens" in att.tournaments()]],
      ["Seniors", [att for att in real_attendees if "seniors" in att.tournaments()]],
      ["Die-hard", [att for att in real_attendees if "diehard" in att.tournaments()]],
      [],
      ["Dining"],
      ["Banquet Admission", [att for att in real_attendees if att.is_attending_banquet()]],
      ["Meal Plans", sum([pri.party_meal_plan().num_meal_plans() for pri in primaries if pri.party_meal_plan() is not None])],
      [],
      ["Translators"],
      ["Chinese", [att for att in translators if "chinese" in att.languages()]],
      ["Korean", [att for att in translators if "korean" in att.languages()]],
      ["Japanese", [att for att in translators if "japanese" in att.languages()]],
      ["Spanish", [att for att in translators if "spanish" in att.languages()]],
      [],
      ["Hospitality", "# Booked"],
      ["Double-occupancy Dorm Bed", sum([item.num_units() for item in housing if item.is_dorm_double()])],
      ["Single-occupancy Dorm Room", sum([item.num_units() for item in housing if item.is_dorm_single()])],
      ["Kitchenette (1 room of 2)", sum([item.num_units() for item in housing if item.is_apt1_1room()])],
      ["Kitchenette (both rooms)", sum([item.num_units() for item in housing if item.is_apt1_2room()])],
      ["Full Kitchen (1 room of 2)", sum([item.num_units() for item in housing if item.is_apt2_1room()])],
      ["Full Kitchen (both rooms)", sum([item.num_units() for item in housing if item.is_apt2_2room()])],
      [],
      ["Housing Occupancy", "# Beds Booked", "# Beds", "% Occupied"],
      ["Dorm Beds", num_dorm_beds_booked, 636, "%.02f%%" % (100 * num_dorm_beds_booked/636.0)],
      ["Kitchenette Bedrooms", num_apt1_beds_booked, 96, "%.02f%%" % (100 * num_apt1_beds_booked/96.0)],
      ["Kitchen Bedrooms", num_apt2_beds_booked, 127, "%.02f%%" % (100 * num_apt2_beds_booked/127.0)],
      ["VIP Bedrooms", num_vip_beds_booked, 8, "%.02f%%" % (100 * num_vip_beds_booked/8.0)],
      [],
      ["T-Shirt Sizes"],
      ["None",              sum(1 for att in real_attendees if att.info()["tshirt"] == "None")],
      ["Youth",             sum(1 for att in real_attendees if att.info()["tshirt"] == "Youth")],
      ["Adult - Small",     sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - Small")],
      ["Adult - Medium",    sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - Medium")],
      ["Adult - Large",     sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - Large")],
      ["Adult - X-Large",   sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - X-Large")],
      ["Adult - XX-Large",  sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - XX-Large")],
      ["Adult - XXX-Large", sum(1 for att in real_attendees if att.info()["tshirt"] == "Adult - XXX-Large")],
    ]

    sheet_header = ["", "Total", "Youth (0-17)", "YA (18-23)", "Adults", "", "Parties of 1", "Parties of 2", "Parties of 3", "Parties of 4", "Parties of 5+"]
    sheet_data = [sheet_header] + [self.render_row(row) for row in row_defs]
    service = authenticate_service_account()
    create_sheet_if_not_exists(service, "Attendee Status", secret("folder_id"), "Aggregate")
    update_sheets_worksheet(service, "Attendee Status", sheet_data, secret("folder_id"), "Aggregate")
