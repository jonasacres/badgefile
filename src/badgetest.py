#!/usr/bin/env python

import sys
import os
import time

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

