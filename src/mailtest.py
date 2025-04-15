#!/usr/bin/env python

import sys
import os
import time

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.emails.email_test import EmailTest
from util.secrets import secret, override_secret

if len(sys.argv) <= 1:
    print("usage: mailtest.py template_name [override_email]")
    print("sends the designated template to a hard-coded test account (namely, jonas)")
    print("if the override_email is set, the test e-mail is sent to that address instead, but using jonas's account info")

if not secret("email_enable"):
    delay = 3
    print("WARNING: This environment has email_enable configured to be false, which means emails do not get sent.")
    print("This is obviously counterproductive for this script.")
    print("Therefore, this script will OVERRIDE this safety setting and send e-mails anyway.")
    print("Hit CTRL+C to abort.")
    print(f"Waiting {delay} seconds...")
    for i in range(delay, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    # Override the email_enable setting to force sending emails
    override_secret("email_enable", True)
    print("Override in place. This session WILL send live e-mails.")

template = sys.argv[1]

badgefile = Badgefile()
email_test = EmailTest(badgefile)
jonas = badgefile.lookup_attendee(24723)

if jonas is None:
    print("Couldn't find test account")
    os._exit(1)

if len(sys.argv) >= 3:
    override_email = sys.argv[2]
    jonas.info()['email'] = override_email

email_test.send(template, [jonas])

