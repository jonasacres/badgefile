#!/usr/bin/env python

import pathlib
import sys
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.html.friends_of_congress_page import DonorPage
from datasources.clubexpress.donations_report import DonationsReport


if "download" in sys.argv:
  log.info("Downloading donations report")
  DonationsReport.download()

