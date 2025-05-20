#!/usr/bin/env python3

# Add the src directory to the Python path
import os
import pathlib
import sys
import argparse

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from server.webservice import WebService
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
    
    print(f"Starting WebService on {args.interface}:{args.port}")
    service.run()
  except Exception as e:
    print(f"Error starting WebService: {e}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
  main()
