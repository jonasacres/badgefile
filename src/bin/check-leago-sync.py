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
from integrations.leago import Leago, aga_badge_to_leago
from util.secrets import secret

def main():
  badgefile = Badgefile()
  leago = Leago("https://api.leago.gg", "https://id.leago.gg", secret("leago_event_key"))
  leago.login()

  participants = [attendee for attendee in badgefile.attendees() if attendee.is_participant()]
  registrations = leago.get_registrations()
  leago.get_tournaments()
  leago_enrollments = {name: leago.get_tournament_players(tournament) for name, tournament in leago.tournaments_by_name.items()}
  defects = 0

  for attendee in participants:
    str_id = str(attendee.id())
    registration = registrations.get(str_id)
    fi = attendee.final_info()

    if not registration:
      print(f"Attendee {attendee.full_name()} {attendee.id()} ({fi.get('badge_rating')}) not found in Leago")
      defects += 1
      continue


    if registration.get("givenName") != fi.get("name_given"):
      print(f"Attendee {attendee.full_name()} {attendee.id()} has incorrect given name in Leago")
      defects += 1

    if registration.get("familyName") != fi.get("name_family"):
      print(f"Attendee {attendee.full_name()} {attendee.id()} has incorrect family name in Leago")
      defects += 1

    checked_in_leago = registration.get("status") == 1
    checked_in_badgefile = attendee.is_checked_in()

    if checked_in_leago != checked_in_badgefile:
      print(f"Attendee {attendee.full_name()} {attendee.id()} has incorrect check-in status in Leago; expected {checked_in_badgefile}, got {checked_in_leago}")
      defects += 1

    tournaments = ["open", "masters", "seniors", "womens", "diehard"]
    for tournament in tournaments:
      players = leago_enrollments[tournament]
      attendee_in_tournament = str(attendee.id()) in players
      if attendee_in_tournament != attendee.is_in_tournament(tournament):
        print(f"Attendee {attendee.full_name()} {attendee.id()} has incorrect {tournament} tournament enrollment in Leago; expected {attendee.is_in_tournament(tournament)}, got {attendee_in_tournament}")
        defects += 1
    
    expected_leago_rating = aga_badge_to_leago(fi['badge_rating'])
    actual_leago_rating = registration.get("rankId")

    if expected_leago_rating != actual_leago_rating:
      print(f"Attendee {attendee.full_name()} {attendee.id()} has incorrect rating in Leago; expected {expected_leago_rating}, got {actual_leago_rating}")
      defects += 1
  
  for registration_id, registration in registrations.items():
    try:
      int_id = int(registration_id)
    except ValueError:
      print(f"Registration {registration_id} has invalid ID")
      defects += 1
      continue
    
    attendee = badgefile.lookup_attendee(int_id)
    if not attendee:
      print(f"Registration {registration_id} has no attendee")
      defects += 1
      continue
  
  print(f"Defects: {defects}")

if __name__ == "__main__":
  main()

