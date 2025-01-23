#!/usr/bin/env python3

# let's not do a daemon. if those fall over, people get mad.
# instead, let's do a cronjob that pulls data from each source.
# then I can also run whatever I want manually, whenever I want.
#
# select what we're doing with a command line argument.

# UPDATE TASK
# pull CE reports
# pull the TD list
# pull the Google Sheets overrides
# as we pull each report
#   save a copy
#   create appropriate top-level object (eg. Reglist)
#   break into row-level objects (eg. ReglistRow)
#   create appropriate journal entries for each object
# update the database with the new journal entries
# update the override sheet

from datamgmt.clubexpress.reglist import Reglist
from datamgmt.badgefile import Badgefile
from datamgmt.clubexpress.activity_list import ActivityList
from datamgmt.tdlist import TDList
from datamgmt.util import *
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

# ANALYSIS TASK
# for each attendee
#   for each issuecheck
#     does attendee already have this issue recorded in db?
#       does the attendee flag this issuecheck?
#         ensure db row matches current issuecheck data
#       else
#         mark issuecheck as resolved
#     else
#       does the attendee flag this issuecheck?
#         create a new issue record in the db

# REPORTING TASK
# TODO: figure out what reports we want to provide
#       maybe a CSV of every registration issue?
# update the registration stats sheet

# ARTIFACT TASK
# for each attendee
#   regenerate badge
#   regenerate checksheet
#   regenerate badgeproof
# regenerate contact directory

# NOTIFICATION TASK
# for each attendee
#   assemble e-mail from outstanding issues
#   TODO: business logic to decide if it's appropriate to e-mail this person right now,
#         based on current issues, when we last e-mailed them and what was in that e-mail
#   send email if appropriate

# WEB TASK
# run the web service; this part has to be a daemon
