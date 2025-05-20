#!/usr/bin/env python

import pathlib
import sys
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.pdfs.scansheet import ScanSheet

badgefile = Badgefile()
scansheet = ScanSheet(badgefile)
scansheet.draw()

print(f"Generated {scansheet.path}")
