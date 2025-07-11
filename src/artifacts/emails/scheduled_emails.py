from model.event import Event
from integrations.email import Email
from model.email_history import EmailHistory
from log.logger import log
from datetime import datetime, timezone, timedelta

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
    
    def eligible_for_housing_reduction_warning(attendee):
      if datetime.now() >= datetime(2025, 6, 14):
        return False
      return eligible_for_housing_reminder(attendee)
    
    def eligible_for_youth_form_reminder(attendee):
      # we don't actually send this e-mail to non-primaries, so this branch is unused.
      # but it's here in case we decide we want it later, and as a safeguard against accidentally blasting every member of a party
      if not attendee.is_primary():
        return attendee.still_needs_youth_form()
      
      for party_member in attendee.party():
        if party_member.still_needs_youth_form():
          return True
      return False
    
    def eligible_for_membership_self(attendee):
      if not attendee.needs_renewal():
        return False # membership does not expire before cutoff date
      if eligible_for_membership_party(attendee):
        return False # we're alread giving them a list of party members with expiring memberships, including them; no need for another email
    
      return True
    
    def eligible_for_membership_party(attendee):
      if not attendee.is_primary():
        return False # stop eligible_for_membership_self from thinking non-primaries are getting this e-mail
      expiring_members = [guest for guest in attendee.party() if guest.needs_renewal()]
      if len(expiring_members) == 1 and expiring_members[0] == attendee:
        return False # there's only one expiring member in the party, and it's the primary; just send the primary an e-mail a membership_self version
      return len(expiring_members) > 0
    
    def eligible_for_no_checkin(attendee):
      # send an e-mail to attendees who intend to play in one of the morning tournaments but didn't check in before registration closed the night before.

      # don't run if we haven't gotten to close of registration yet
      # (July 12, 2025. wait to 11pm central time to make sure we've processed last-minute stuff)
      current_time = datetime.now(timezone.utc)
      reg_close_time = datetime(2025, 7, 12, 23, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
      
      if current_time < reg_close_time:
        return False

      # don't run if we haven't set up the "congress" event
      # (safeguard against 'live' server blasting everyone Sunday morning before I can sync changes from my laptop)
      if not Event.exists("congress"):
        return False
      
      # sanity check: if we haven't checked 100 people in, this probably isn't live post-checkin data :)
      if Event("congress").num_scanned_attendees() < 100:
        return False
      
      # don't send if the player isn't in one of the AM tournaments
      in_morning_tournament = attendee.is_in_open() or attendee.is_in_masters()
      if not in_morning_tournament:
        return False
      
      # check if the player is checked in (e.g. scanned into the "congress" event)
      event = Event("congress")
      num_scans = event.num_times_attendee_scanned(attendee)
      has_checked_in = num_scans > 0

      # send if and only if the player is not checked in
      return not has_checked_in
    
    # convenience variables to make clear how often each email goes out
    only_send_once = None
    send_every_three_days = 60*60*24*3

    # self.run_campaign("1d-excursion-survey",           always_eligible,                        only_send_once,        allow_nonprimary=True)
    self.run_campaign("1e-special-events",             always_eligible,                        only_send_once,        allow_nonprimary=True)
    self.run_campaign("1f-leago-yapp",                 always_eligible,                        only_send_once,        allow_nonprimary=True)
    # self.run_campaign("1g-texas-weather",              always_eligible,                        only_send_once,        allow_nonprimary=True)
    self.run_campaign("1h-final-announcement",         always_eligible,                        only_send_once,        allow_nonprimary=True)
    self.run_campaign("1i-no-checkin",                 eligible_for_no_checkin,                only_send_once,        allow_nonprimary=True)
    # self.run_campaign("3a-housing-reminder",           eligible_for_housing_reminder,          send_every_three_days, allow_nonprimary=False)
    # self.run_campaign("3a2-housing-reduction-warning", eligible_for_housing_reduction_warning, only_send_once,        allow_nonprimary=False)
    # self.run_campaign("3b-transportation-survey",      always_eligible,                        only_send_once,        allow_nonprimary=False)
    self.run_campaign("3c-youth-form-reminder",        eligible_for_youth_form_reminder,       send_every_three_days, allow_nonprimary=False)
    self.run_campaign("3d1-membership-self",           eligible_for_membership_self,           send_every_three_days, allow_nonprimary=True)
    self.run_campaign("3d2-membership-party",          eligible_for_membership_party,          send_every_three_days, allow_nonprimary=False)

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
        email = Email(email_template, attendee, extra = self.extra_for_template(email_template, attendee))
        email.send(force=True)
  
  def extra_for_template(self, template, attendee):
    if template == "3c-youth-form-reminder":
      youth_form_li = ""
      for party_member in attendee.party():
        if party_member.still_needs_youth_form():
          kid_info = party_member.info()
          youth_form_li += f"<li>{kid_info['name_given']} {kid_info['name_family']} (age {party_member.age_at_congress()})</li>\n"
      return {'youth_form_li': youth_form_li}
    if template == "3d2-membership-party":
      expiring_members = [guest for guest in attendee.party() if guest.needs_renewal()]
      renewal_table = ""
      for member in expiring_members:
        info = member.info()
        renewal_table += f"<tr><th scope=\"row\">{info['name_given']} {info['name_family']}</th><td>{info['aga_id']}</td><td>{info['aga_expiration_date']}</td></tr>\n"
      return {'renewal_table': renewal_table}
    return {}
  