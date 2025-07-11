#!/usr/bin/env python3

import time
import pathlib
import sys

# Add the src directory to the Python path
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from server.webservice import WebService
from server.socketserver import SocketServer
from model.badgefile import Badgefile
from model.event import Event

def main():
  print("WARNING: This will nuke the congress check-in database and mark every attendee as eligible for check-in. Hit CTRL-C to abort.")
  for i in range(5, 0, -1):
    print(f"{i}...")
    time.sleep(1)

  try:
    badgefile = Badgefile()
    
    event = Event("congress") # create the test event if it doesn't exist already
    event.nuke()

    print("Nuked congress check-in database.")

    # mark every attendee as eligible
    attendees = badgefile.attendees()
    for attendee in badgefile.attendees():
      event.mark_attendee_eligible(attendee)

    print(f"Done. Marked {len(attendees)} attendees as eligible.")
    
  except Exception as e:
    print(f"Error starting WebService: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
  main()
