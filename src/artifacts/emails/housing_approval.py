from integrations.email import Email
from model.email_history import EmailHistory
from log.logger import log

class HousingApprovalEmail:
  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def recipients(self):
    # everyone who is approved for housing and didn't get the approval e-mail yet (which has a youth version and adult version)
    all_approved = [attendee for attendee in self.badgefile.attendees() if attendee.is_housing_approved() and attendee.is_primary()]
    all_emailed_adult = EmailHistory.shared().recipients_for_email("2b-housing-approved-adult")
    all_emailed_youth = EmailHistory.shared().recipients_for_email("2c-housing-approved-youth")

    not_emailed = [att for att in all_approved if att.id() not in all_emailed_adult and att.id() not in all_emailed_youth]
    return not_emailed
  
  def send(self):
    recipients = self.recipients()
    if len(recipients) > 0:
      log.info(f"Sending housing approval e-mail to {len(recipients)} recipients")
    
    for attendee in self.recipients():
      template = self.template_for_recipient(attendee)
      log.debug(f"Sending {template} to attendee {attendee.full_name()} (#{attendee.id()})")
      Email(template, attendee).send()
    
    EmailHistory.shared().sync_emails()
  
  def template_for_recipient(self, attendee):
    has_youth = any([party_member.age_at_congress() <= 22 for party_member in attendee.party()])
    return "2c-housing-approved-youth" if has_youth else "2b-housing-approved-adult"
  