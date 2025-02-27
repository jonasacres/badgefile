from datetime import datetime
from integrations.google_api import sync_sheet_table, authenticate_service_account
from model.email_history import EmailHistory
from util.secrets import secret

from log.logger import log

class EmailReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile

  def email_row(self, attendee, email_types):
    emails = EmailHistory.shared().latest_emails_for_user(attendee.id())
    info = attendee.info()
    
    email_columns = [
      f'=HYPERLINK("{emails[type]["email_copy_url"]}", "{datetime.strptime(emails[type]["timestamp"], "%Y-%m-%d %H:%M:%S").strftime("%-m/%-d/%Y")}")' if type in emails
      else ''
      for type in email_types
    ]

    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      info["email"],
      "Yes" if attendee.is_primary() else "No",
    ] + email_columns

  def update(self):
    email_types = EmailHistory.shared().email_types()

    sheet_header = [
      "Name",
      "AGAID",
      "Email",
      "Is Primary?",
    ] + email_types
    
    attendee_list = [att for att in self.badgefile.attendees() if att.is_primary() or len(EmailHistory.shared().latest_emails_for_user(att.id())) > 0]
    sheet_data = [self.email_row(attendee, email_types) for attendee in attendee_list]
    service = authenticate_service_account()
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Emails", secret("folder_id"), valueInputOption='USER_ENTERED')


