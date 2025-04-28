#!/usr/bin/env python

import sys
import os
import time

from model.badgefile import Badgefile
from util.util import *
from log.logger import log
from artifacts.html.friends_of_congress_page import DonorPage
from datasources.clubexpress.payments_report import PaymentsReport


if "download" in sys.argv:
  log.info("Downloading payments report")
  PaymentsReport.download()

badgefile = Badgefile()
DonorPage(badgefile).generate().upload()
print("Generated donor page")
