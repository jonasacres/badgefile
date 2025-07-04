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
lyra = badgefile.lookup_attendee(24793)
peter = badgefile.lookup_attendee(24807)
kevin = badgefile.lookup_attendee(30478)
anchi = badgefile.lookup_attendee(1000090)
AttendeeStatusSource(badgefile).read_tournament_overrides()
MastersSheet(badgefile).read_sheet()

test_attendees = [
    lyra,
    peter,
    # kevin,
    anchi,
]

for attendee in test_attendees:
    attendee.badge().generate()

for attendee in badgefile.attendees():
    if attendee.is_cancelled():
        continue
    if not attendee.badge().already_exists():
        print(attendee.full_name())
        attendee.badge().generate()
        print(f"Generated badge: {attendee.badge().path()}")


