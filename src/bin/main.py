#!/usr/bin/env python3

import sys
import os
import time
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from model.badgefile import Badgefile
from datasources.clubexpress.reglist import Reglist
from datasources.clubexpress.activity_list import ActivityList
from datasources.clubexpress.housing_activity_list import HousingActivityList
from datasources.clubexpress.housing_reglist import HousingReglist
from datasources.clubexpress.payments_report import PaymentsReport
from datasources.tdlist import TDList
from artifacts.emails.scheduled_emails import ScheduledEmails
from util.util import *
from log.logger import log


def download():
  log.notice(f"Downloading fresh data.")
  
  log.info(f"Downloading reglist.")
  try:
    Reglist.download()
  except Exception as exc:
    log.critical("Failed to dowload reglist", exception=exc)

  log.info(f"Downloading activity list.")
  try:
    ActivityList.download()
  except Exception as exc:
    log.critical("Failed to download activity list", exception=exc)

  log.info(f"Downloading housing reglist.")
  try:
    HousingReglist.download()
  except Exception as exc:
    log.critical("Failed to dowload housing reglist", exception=exc)

  log.info(f"Downloading housing activity list.")
  try:
    HousingActivityList.download()
  except Exception as exc:
    log.critical("Failed to download housing activity list", exception=exc)

  log.info(f"Downloading TD list.")
  try:
    TDList.download()
  except Exception as exc:
    log.critical("Failed to download TD list", exception=exc)

  log.info(f"Downloading payments report.")
  try:
    PaymentsReport.download()
  except Exception as exc:
    log.critical("Failed to download payments report", exception=exc)

def update():
  if Reglist.latest() == None:
    Reglist.download()
  if ActivityList.latest() == None:
    ActivityList.download()
  if HousingReglist.latest() == None:
    HousingReglist.download()
  if HousingActivityList.latest() == None:
    HousingActivityList.download()
  if TDList.latest() == None:
    TDList.download()
  if PaymentsReport.latest() == None:
    PaymentsReport.download()

  log.notice(f"Updating badgefile.")
  bf = Badgefile()
  bf.update()
  bf.update_attendees()
  bf.run_approvals()

  # log.notice("Running scheduled e-mails.")
  # ScheduledEmails.run_campaigns(bf)

start_time = time.time()
log.notice(f"=======================================")
log.notice(f"Invoked as '{' '.join(sys.argv)}', pwd '{os.getcwd()}'")
log.notice(f"Git: {git_summary()}")

try:
  if "download" in sys.argv:
    download()
  update()

  log.notice(f"Complete. Runtime: {time.time() - start_time:.03f}s")
except Exception as exc:
  log.fatal("Uncaught exception", exception=exc)
