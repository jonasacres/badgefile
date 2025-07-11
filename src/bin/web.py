#!/usr/bin/env python3

# Add the src directory to the Python path
import os
import pathlib
import sys
import argparse
import time

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from server.socketserver import SocketServer
from server.webservice import WebService
from model.badgefile import Badgefile
from model.event import Event
from model.leago_sync import LeagoSync
from log.logger import log
from artifacts.generated_reports.as_overview import OverviewReport
from model.notification_manager import NotificationManager

import threading

class OverviewUpdater:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    self.last_update = None
    self.dirty = False
  
    def received_notification(key, notification):
      attendee = notification.get("attendee")
      if attendee:
        self.dirty = True
    
    NotificationManager.shared().observe(received_notification)
    thread = threading.Thread(target=self.run, daemon=True)
    thread.start()
  
  def run(self):
    log.info(f"Starting overview updater thread")
    while True:
      time.sleep(0.1)
      try:
        update_ok = self.last_update is None or time.time() - self.last_update > 10
        if self.dirty and update_ok:
          log.info(f"Updating overview")
          OverviewReport(self.badgefile).update()
          self.dirty = False
          self.last_update = time.time()
      except Exception as exc:
        log.error(f"Error in overview update thread", exception=exc)
        time.sleep(10)

def main():
  parser = argparse.ArgumentParser(description='Start the Go Congress WebService')
  parser.add_argument('--interface', default='127.0.0.1',
                      help='Interface to listen on (default: 127.0.0.1)')
  parser.add_argument('--port', type=int, default=8080,
                      help='Port to listen on (default: 8080)')
  
  args = parser.parse_args()

  
  try:
    badgefile = Badgefile()
    leago_sync = LeagoSync(badgefile)
    leago_sync.run()
    leago_sync.sync_all()

    service = WebService(badgefile, 
                        listen_interface=args.interface, 
                        port=args.port)
    
    SocketServer.shared().listen()
    updater = OverviewUpdater(badgefile)

    print(f"Starting WebService on {args.interface}:{args.port}")
    service.run()
  except Exception as e:
    print(f"Error starting WebService: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
  main()
