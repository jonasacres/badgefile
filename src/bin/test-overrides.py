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
overrides = AttendeeStatusSource(badgefile).read_manual_badge_data()
for override in overrides:
  print(f"Override: {override}")
  if override['badgefile_id'] != '':
    attendee = badgefile.lookup_attendee(override['badgefile_id'])
    if attendee is None:
      log.warn(f"Unable to find attendee for overridden badge with id {override['badgefile_id']}, description '{override['description']}'")
      continue
    attendee.set_manual_override(override)
