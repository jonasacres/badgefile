from integrations.google_api import sync_sheet_table, authenticate_service_account
from util.secrets import secret

from log.logger import log

class TournamentsReport:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    pass

  def tournament_attendee_row(self, attendee):
    info = attendee.info()
    tournaments = attendee.tournaments()
    issues = attendee.issues_in_category('tournament')
    problems = " | ".join([issue['msg'] for issue in issues])
    
    return [
      f"{info['name_family']}, {info['name_given']} {info['name_mi'] if info['name_mi'] else ''}",
      attendee.id(),
      info['email'],
      attendee.phone(),
      attendee.age_at_congress(),
      info['country'],

      "YES" if 'masters' in tournaments else "NO",
      "YES" if 'open'    in tournaments else "NO",
      "YES" if 'womens'  in tournaments else "NO",
      "YES" if 'seniors' in tournaments else "NO",
      "YES" if 'diehard' in tournaments else "NO",

      attendee.aga_rating(),
      "YES" if attendee.rating_override_requested() else "NO",
      "YES" if len(issues) > 0 else "NO",
      problems
    ]

  def update(self):
    sheet_header = [
      "Name",
      "AGAID",
      "Email",
      "Phone",
      "Age at Congress",
      "Country of Origin",
      "Masters?",
      "Open?",
      "Womens?",
      "Seniors?",
      "Diehard?",
      "Official rating",
      "Request override?",
      "Needs Review?",
      "Problems",
      "TD Override",
      "Registrar Comments",
    ]
    
    sheet_data = [self.tournament_attendee_row(att) for att in self.badgefile.attendees() if att.is_participant()]
    service = authenticate_service_account()
    
    log.debug("tournaments_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Tournaments", secret("folder_id"))


