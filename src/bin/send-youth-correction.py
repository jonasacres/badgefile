#!/usr/bin/env python3

import time
import pathlib
import sys
from datetime import datetime, timedelta

# Add the src directory to the Python path
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from server.webservice import WebService
from server.socketserver import SocketServer
from model.badgefile import Badgefile
from model.event import Event
from model.email_history import EmailHistory
from integrations.database import Database
from integrations.email import Email

def main():
  badgefile = Badgefile()
  
  # Get current time and calculate 6 hours ago
  now = datetime.now()
  six_hours_ago = now - timedelta(hours=6)
  
  # Query database directly for badgefile_ids that received 3c-youth-form-reminder in last 6 hours
  results = Database.shared().query("""
    SELECT DISTINCT badgefile_id
    FROM email_history
    WHERE email_type = '3c-youth-form-reminder'
    AND timestamp >= ?
    ORDER BY badgefile_id
  """, [six_hours_ago])
  
  recent_recipient_ids = [row['badgefile_id'] for row in results]
  print(f"Found {len(recent_recipient_ids)} attendees who received 3c-youth-form-reminder in the last 6 hours")
  
  # Filter to those who have submitted all needed youth forms
  needs_correction = []
  deserved_email = []
  for attendee_id in recent_recipient_ids:
    attendee = badgefile.lookup_attendee(attendee_id)
    if attendee:
      # Check if any party member still needs youth form
      party_member_needs_form = False 
      for party_member in attendee.party():
        if party_member.still_needs_youth_form():
          party_member_needs_form = True
          deserved_email.append(attendee)
          break
      if not party_member_needs_form and attendee.is_primary():
        needs_correction.append(attendee)
  
  print(f"Found {len(needs_correction)} attendees who need a youth form correction.")
  
  # Send correction email to each attendee who received reminder in error
  for attendee in needs_correction:
    print(f"Sending correction to {attendee.name_given()}")
    attendee.send_email("youth-form-correction")
  
  email = Email("youth-form-correction.txt", attendee)
  email.send(force=True)

if __name__ == "__main__":
  main()
