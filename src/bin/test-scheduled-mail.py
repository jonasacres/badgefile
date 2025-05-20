#!/usr/bin/env python
 
import sys
import os
import time
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from artifacts.emails.scheduled_emails import ScheduledEmails
from integrations.email import Email
from log.logger import log
from util.secrets import secret, override_secret

bf = Badgefile()
Email.override_enable()

ScheduledEmails.run_campaigns(bf)
