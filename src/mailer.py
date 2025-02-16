#!/usr/bin/env python3

from integrations.email import Email, connect_smtp
from log.logger import log
from model.badgefile import Badgefile
import sys
import time

def send_emails(template, recipients):
  server = connect_smtp()

  try:
    log.info(f"Sending email {template} to {len(recipients)} recipients")
    for recipient in recipients:
      email = Email(template, recipient)
      # email.send(server)
  finally:
    log.info("Done sending e-mails")
    server.quit()

if __name__ == "__main__":
  log.debug("Loading badgefile")
  badgefile = Badgefile()

  # Get all primary registrants
  recipients = [att for att in badgefile.attendees() if att.is_primary() and not att.is_cancelled()]

  if len(sys.argv) < 2:
    print("Usage: mailer.py <template>")
    sys.exit(1)

  template = sys.argv[1]
  sample_email = Email(template, recipients[0])
  sample_subject, sample_body = sample_email.apply_template()

  print(f"Template: {template}")
  print(f"Subject: {sample_subject}")
  print(f"Body:\n{sample_body}\n\n")

  print(f"\033[91mWill send template '\033[1m{template}\033[0m\033[91m' to all {len(recipients)} primary registrants in 10 seconds...\033[0m")
  print("Press CTRL+C to cancel")
  time.sleep(10)
  send_emails(template, recipients)
