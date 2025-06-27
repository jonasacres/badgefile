#!/usr/bin/env python

# just sits in a loop and makes sure the authentication token is fresh

import sys
import time
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from log.logger import log
from util.secrets import secret
from integrations.leago import Leago
from model.badgefile import Badgefile

leago = Leago("https://api.leago.gg", "https://id.leago.gg", secret("leago_event_key"))

token = leago.get_access_token()
if not token:
  leago.login()

last_value = None
while True:
  time.sleep(1)
  token = leago.get_access_token()

  value = len(leago.get_registrations(force=True))
  if value != last_value:
    last_value = value
    log.info(f"new value: {value}")

  if not token:
    log.warn("Oh no! The leago token expired. Run leago-authenticate on this host to get one.")
    sys.exit(1)
