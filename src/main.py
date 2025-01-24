#!/usr/bin/env python3

from model.badgefile import Badgefile
from datasources.clubexpress.reglist import Reglist
from datasources.clubexpress.activity_list import ActivityList
from datasources.tdlist import TDList
from util.util import *
from log.logger import log
import sys
import time
import os

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

  log.info(f"Downloading TD list.")
  try:
    TDList.download()
  except Exception as exc:
    log.critical("Failed to download TD list", exception=exc)

def update():
  if Reglist.latest() == None:
    Reglist.download()
  if ActivityList.latest() == None:
    ActivityList.download()
  if TDList.latest() == None:
    TDList.download()

  log.notice(f"Updating badgefile.")
  bf = Badgefile()
  bf.update()


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
