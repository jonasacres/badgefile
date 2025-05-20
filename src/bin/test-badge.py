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
jonas = badgefile.lookup_attendee(24723)

if jonas is None:
    print("Couldn't find test account")
    os._exit(1)

jonas.badge().generate()
print(f"Generated badge: {jonas.badge().path()}")

