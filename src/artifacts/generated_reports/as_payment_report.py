from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class PaymentReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def payment_attendee_row(self, attendee):
    info = attendee.info()
    
    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      info['email'],
      attendee.phone(),
      attendee.age_at_congress(),
      info['country'],
      len(attendee.party()),
      attendee.congress_total_fees(),
      attendee.congress_balance_due(),
      attendee.housing_total_fees(),
      attendee.housing_balance_due(),
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGAID",
      "Email",
      "Phone",
      "Age at Congress",
      "Country of Origin",
      "Party Size",
      "Congress Fees",
      "Congress Balance Due",
      "Housing Fees",
      "Housing Balance Due",
      "Comments (Editable)",
    ]
    
    sheet_data = [self.payment_attendee_row(att) for att in self.badgefile.attendees() if att.is_primary()]
    service = authenticate_service_account()
    
    log.debug("payments_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Payment", secret("folder_id"))


