#!/usr/bin/env python

import pathlib
import sys
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from datasources.sheets.housing_sheet import HousingSheet

badgefile = Badgefile()
HousingSheet(badgefile).read_sheet()