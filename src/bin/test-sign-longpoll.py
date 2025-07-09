#!/usr/bin/env python3

import threading
import time
import os
import pathlib
import sys
import argparse

# Add the src directory to the Python path
src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from server.webservice import WebService
from server.socketserver import SocketServer
from model.badgefile import Badgefile
from model.event import Event

def main():
  parser = argparse.ArgumentParser(description='Start the Go Congress WebService')
  parser.add_argument('--interface', default='127.0.0.1',
                    help='Interface to listen on (default: 127.0.0.1)')
  parser.add_argument('--port', type=int, default=8080,
                    help='Port to listen on (default: 8080)')
  
  args = parser.parse_args()
  
  try:
    badgefile = Badgefile()
    service = WebService(badgefile, 
                      listen_interface=args.interface, 
                      port=args.port)
    
    event = Event("congress") # create the test event if it doesn't exist already

    # mark every attendee as eligible, and reset their scan count to zero
    for attendee in badgefile.attendees():
      event.mark_attendee_eligible(attendee)
      event.scan_in_attendee(attendee, is_reset=True)
    
    # Create a thread to continuously scan attendees    
    def scan_attendees_thread():
      while True:
        # Scan each attendee one by one with a delay
        for attendee in badgefile.attendees():
          event.scan_in_attendee(attendee)
          time.sleep(10)
        
        # Reset all attendees at the end of each cycle
        for attendee in badgefile.attendees():
          event.scan_in_attendee(attendee, is_reset=True)
    
    # Start the scanning thread
    scan_thread = threading.Thread(target=scan_attendees_thread, daemon=True)
    scan_thread.start()

    SocketServer.shared().listen()

    print(f"Starting WebService on {args.interface}:{args.port}")
    service.run()
  except Exception as e:
    print(f"Error starting WebService: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
  main()
