#!/usr/bin/env python3

import sys
import os
import time
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from datasources.clubexpress.reglist import Reglist
from datasources.clubexpress.housing_reglist import HousingReglist
from datasources.clubexpress.registration_fees_charges_congress import RegistrationFeesChargesCongress
from datasources.clubexpress.registration_fees_charges_housing import RegistrationFeesChargesHousing
from artifacts.generated_reports.checkin_status import CheckinStatusReport
from util.util import *
from log.logger import log

if "download" in sys.argv:
  Reglist.download()
  RegistrationFeesChargesCongress.download()
  RegistrationFeesChargesHousing.download()

bf = Badgefile()

CheckinStatusReport(bf).generate("artifacts/checkin_report.csv")