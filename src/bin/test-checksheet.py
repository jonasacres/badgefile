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
lyra = badgefile.lookup_attendee(24793)

if lyra is None:
  print("Couldn't find test account")
  os._exit(1)

# lyra.checksheet().generate()
# checksheet_path = lyra.checksheet().path()
# print(f"Generated checksheet: {checksheet_path}")

for attendee in badgefile.attendees():
  if attendee.is_cancelled():
    continue
  if not os.path.exists(attendee.checksheet().path()):
    attendee.checksheet().generate()
    print(f"Generated checksheet: {attendee.checksheet().path()}")

