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
from integrations.email import Email

if len(sys.argv) <= 1:
    print("usage: mailtest.py template_name [override_email]")
    print("sends the designated template to a hard-coded test account (namely, jonas)")
    print("if the override_email is set, the test e-mail is sent to that address instead, but using jonas's account info")

Email.override_enable()

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

