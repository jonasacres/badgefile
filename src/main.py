#!/usr/bin/env python3

from datamgmt.clubexpress.reglist import Reglist
from datamgmt.badgefile import Badgefile
from datamgmt.clubexpress.activity_list import ActivityList
from datamgmt.tdlist import TDList
from util.util import *
from log.logger import *
import sys
import time

def download():
  log_notice(f"Downloading fresh data.")
  
  log_info(f"Downloading reglist.")
  try:
    Reglist.download()
  except Exception as exc:
    log_critical("Failed to dowload reglist", exception=exc)

  log_info(f"Downloading activity list.")
  try:
    ActivityList.download()
  except Exception as exc:
    log_critical("Failed to download activity list", exception=exc)

  log_info(f"Downloading TD list.")
  try:
    TDList.download()
  except Exception as exc:
    log_critical("Failed to download TD list", exception=exc)

def update():
  if Reglist.latest() == None:
    Reglist.download()
  if ActivityList.latest() == None:
    ActivityList.download()
  if TDList.latest() == None:
    TDList.download()

  log_notice(f"Updating badgefile.")
  bf = Badgefile()
  bf.update()


start_time = time.time()
log_notice(f"=======================================")
log_notice(f"Invoked as '{' '.join(sys.argv)}', pwd '{os.getcwd()}'")
log_notice(f"Git: {git_summary()}")

try:
  if "download" in sys.argv:
    download()
  update()
  log_notice(f"Complete. Runtime: {time.time() - start_time:.03f}s")
except Exception as exc:
  log_fatal("Uncaught exception", exception=exc)
