#!/usr/bin/env python

import sys
import os
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log

badgefile = Badgefile()
badgefile.fast_update()

for attendee in badgefile.attendees():
  if attendee.is_cancelled():
    continue
  if not attendee.badge().already_exists():
    attendee.badge().generate()
    print(f"Generated badge: {attendee.badge().path()}")
  if not attendee.checksheet().already_exists():
    attendee.checksheet().generate()
    print(f"Generated checksheet: {attendee.checksheet().path()}")
