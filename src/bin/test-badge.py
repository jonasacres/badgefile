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

for i in range(1, 7):
    lyra.badge().generate(f"src/static/badge_art/{i}.png")
    badge_path = lyra.badge().path()
    badge_path = badge_path[:-4]  # Remove .pdf suffix
    badge_path = f"{badge_path}-{i}.pdf"
    os.rename(lyra.badge().path(), badge_path)
    print(f"Generated badge: {badge_path}")


