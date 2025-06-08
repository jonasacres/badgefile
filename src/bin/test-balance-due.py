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
from util.util import *
from log.logger import log

if "download" in sys.argv:
  Reglist.download()
  RegistrationFeesChargesCongress.download()
  RegistrationFeesChargesHousing.download()

bf = Badgefile()
# bf.update()

for attendee in bf.attendees():
  print(f"Attendee {attendee.id()} {attendee.full_name()}: ${attendee.balance_due()} (congress ${attendee.congress_balance_due()}, housing ${attendee.housing_balance_due()})")
