#!/usr/bin/env python

import sys
import os
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from datasources.sheets.masters_sheet import MastersSheet
from datasources.sheets.attendee_status import AttendeeStatusSource

badgefile = Badgefile()
AttendeeStatusSource(badgefile).read_tournament_overrides()
MastersSheet(badgefile).read_sheet()


for attendee in badgefile.attendees():
  if (not attendee.badge_rating() or attendee.badge_rating() == "") and attendee.is_participant() and not attendee.is_cancelled():
    ai = attendee.info()
    print(f"#{attendee.id()} {attendee.full_name()} -- No rating. tournaments='{','.join(attendee.tournaments())}', age={attendee.age_at_congress()}")
