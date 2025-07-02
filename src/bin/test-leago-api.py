#!/usr/bin/env python

import sys
import pathlib

src_path = pathlib.Path(__file__).parent.parent
sys.path.append(str(src_path))

from log.logger import log
from util.secrets import secret
from integrations.leago import Leago
from model.badgefile import Badgefile
from datasources.sheets.attendee_status import AttendeeStatusSource

badgefile = Badgefile()
AttendeeStatusSource(badgefile).read_tournament_overrides()

leago = Leago("https://api.leago.gg", "https://id.leago.gg", secret("leago_event_key"))
leago.login()

for tournament_title, tournament in leago.get_tournaments().items():
  print(f"Tournament: {tournament.get('title', 'no title')} [{tournament.get('key', 'no key')}] ({tournament.get('description', 'no description')})")

for registration_id, registration in leago.get_registrations().items():
  print(f"registration: {registration.get('givenName', 'no given name')} {registration.get('familyName', 'no family name')} [{registration.get('key', 'no key')}] ({registration.get('organizationMemberKey', 'no AGAID')})")

if True:
  # try adding everyone's info
  participants = [attendee for attendee in badgefile.attendees() if attendee.is_participant() and str(attendee.badge_rating()) != '']
  for attendee in participants:
    log.info(f"Syncing #{attendee.id()} {attendee.full_name()} ({attendee.badge_rating()})")
    try:
      leago.sync_attendee_info(attendee)
      leago.sync_attendee_enrollment(attendee)
    except Exception as exc:
      log.info("Failed.", exception=exc)
