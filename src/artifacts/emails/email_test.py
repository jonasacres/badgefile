from integrations.email import Email
from model.email_history import EmailHistory
from log.logger import log

class EmailTest:
  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def send(self, template, recipients):
    if len(recipients) > 0:
      log.info(f"Sending {template} e-mail to {len(recipients)} recipients")
    
    for attendee in recipients:
      log.debug(f"Sending {template} to attendee {attendee.full_name()} (#{attendee.id()})")
      Email(template, attendee).send(force=True)
    
    EmailHistory.shared().sync_emails()
  