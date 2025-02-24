from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class MembershipReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def membership_attendee_row(self, attendee):
    info = attendee.info()
    needs_renewal = any([issue['code'] == '1a' for issue in attendee.issues_in_category('membership')])
    
    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      info['email'],
      attendee.phone(),
      attendee.age_at_congress(),
      info['country'],

      attendee.info().get("member_type", None),
      attendee.membership_expiration().strftime("%m/%d/%Y") if attendee.membership_expiration() else None,
      "RENEW" if needs_renewal else "OK",
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGAID",
      "Email",
      "Phone",
      "Age at Congress",
      "Country of Origin",
      "Member Type",
      "Expiration Date",
      "Needs Renew?",
    ]
    
    sheet_data = [self.membership_attendee_row(att) for att in self.badgefile.attendees() if att.is_participant()]
    service = authenticate_service_account()
    
    log.debug("memberships_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Membership", secret("folder_id"))


