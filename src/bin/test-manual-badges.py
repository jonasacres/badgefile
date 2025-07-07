#!/usr/bin/env python

import sys
import os
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from datasources.sheets.attendee_status import AttendeeStatusSource

badgefile = Badgefile()
badgefile.update_attendees()

for attendee in badgefile.attendees():
  if attendee.is_manual():
    print(f"Attendee: {attendee.id()} | {attendee.full_name()} | {attendee.title()} | {attendee.badge_rating()}")
    print(attendee.final_info())
    print()