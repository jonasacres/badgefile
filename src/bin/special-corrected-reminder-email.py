#!/usr/bin/env python

import sys
import os
import time
import pathlib
import sys

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.emails.email_test import EmailTest
from util.secrets import secret, override_secret
from model.email_history import EmailHistory
from integrations.email import Email
from artifacts.generated_reports.as_email import EmailReport

affected_users = []

try:
  with open(os.path.join(os.path.dirname(__file__), '../../corrected_reminder_email_users.txt'), 'r') as f:
    for line in f:
      email = line.strip()
      if email:  # Skip empty lines
        affected_users.append(email)
except FileNotFoundError:
  log.error("Could not find corrected_reminder_email_users.txt file")
  sys.exit(1)
except Exception as e:
  log.error(f"Error reading corrected_reminder_email_users.txt: {str(e)}")
  sys.exit(1)

if not affected_users:
  log.warning("No email addresses found in corrected_reminder_email_users.txt")

email_template = "3a1-housing-reminder-correction"
badgefile = Badgefile()
attendees = [attendee for attendee in badgefile.attendees() if attendee.info()['email'] in affected_users and attendee.is_primary() and not attendee.is_cancelled() and not attendee.party_housing()]
has_no_hash = [att for att in attendees if att.info()['hash_id'] is None or not all(c in '0123456789abcdef' for c in att.info()['hash_id'])]

if has_no_hash:
  print(f"{len(has_no_hash)} users have no hash.")
  for attendee in has_no_hash:
    print(f"{attendee.id()} {attendee.full_name()} {attendee.info()['email']}")
  print("Some users have invalid hash_ids. Exiting.")
  sys.exit(1)

print(f"Sending email to {len(attendees)} attendees")

Email.override_enable()

for attendee in attendees:
  log.debug(f"Sending e-mail {email_template} to attendee {attendee.full_name()} (#{attendee.id()})")
  email = Email(email_template, attendee)
  email.send(force=True)

EmailHistory.shared().sync_emails()
EmailReport(badgefile).update()
