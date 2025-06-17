#!/usr/bin/env python

import sys
import os
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from datasources.clubexpress.housing_activity_list import HousingActivityList

badgefile = Badgefile()
attendee = badgefile.lookup_attendee(25827)

if attendee is None:
    print("Couldn't find test account")
    os._exit(1)

HousingActivityList.latest().rows(badgefile)
# for act in HousingActivityList.latest().rows(badgefile):
#   if act is None:
#      continue
#   info = act.info()
#   print(f"{info['activity_title']}")
