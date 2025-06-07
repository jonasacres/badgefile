from integrations.email import Email
from model.email_history import EmailHistory
from log.logger import log

class ScheduledEmails:
  @classmethod
  def run_campaigns(cls, badgefile):
    scheduler = cls(badgefile)
    scheduler.run_housing_reminders()
    EmailHistory.shared().sync_emails()

  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def run_housing_reminders(self):
    def always_eligible(attendee):
      return True
    
    def eligible_for_housing_reminder(attendee):
      # they have housing; don't bug them about housing
      if attendee.party_housing():
        return False
      
      # they said they'd arrange their own housing; don't bug them about housing
      if attendee.will_arrange_own_housing():
        return False
      
      # they signed up, but don't have housing, and haven't said they're arranging their own, so remind them to buy housing
      return True
    self.run_campaign("3a-housing-reminder", eligible_for_housing_reminder, 60*60*24*3, allow_nonprimary=False)
    self.run_campaign("3b-transportation-survey", always_eligible, None, allow_nonprimary=False)

  def run_test_campaign(self):
    def eligible_for_test_campaign(attendee):
      return attendee.id() == 24723
    self.run_campaign("3b-transportation-survey", eligible_for_test_campaign, None, allow_nonprimary=True)

  def run_campaign(self, email_template, eligibility_lambda, min_time_between_emails_sec, allow_nonprimary=False):
    history = EmailHistory.shared()
    for attendee in self.badgefile.attendees():
      # most e-mails never target non-primaries, so handle that separately from the lambda to avoid duplication+accidental omission of check
      if not allow_nonprimary and not attendee.is_primary():
        continue

      if attendee.is_cancelled():
        continue

      # Skip if attendee is not eligible
      if not eligibility_lambda(attendee):
        continue
        
      # Check when user last received this email type
      last_email_time = history.most_recent_email_for_user(attendee.id(), email_template)
      
      should_send = False
      if last_email_time is None:
        # Never received this email before
        should_send = True
      else:
        # Check if enough time has passed since the last email
        from datetime import datetime, timedelta
        time_since_last = datetime.now() - last_email_time
        if min_time_between_emails_sec is not None and time_since_last.total_seconds() >= min_time_between_emails_sec:
          should_send = True
      
      if should_send:
        # Create and send the email
        log.debug(f"Sending scheduled e-mail {email_template} to attendee {attendee.full_name()} (#{attendee.id()})")
        email = Email(email_template, attendee)
        email.send(force=True)
