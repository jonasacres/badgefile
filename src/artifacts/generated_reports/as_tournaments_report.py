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
    
    # issues is every issue EXCEPT rank override request (code 6b)
    issues = [issue for issue in attendee.issues_in_category('tournament') if issue['code'] != '6b']
    
    problems = " | ".join([issue['msg'] for issue in issues])
    needs_override = attendee.rating_override_requested() # TODO: we'll want to check against existing "Override Rating" column; if set, this is false
    
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
      "YES" if len(issues) > 0 or needs_override else "NO",
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
      "Override Rating (Editable)",
      "Ignore Problems (Editable)",
      "Comments (Editable)",
    ]
    
    sheet_data = [self.tournament_attendee_row(att) for att in self.badgefile.attendees() if att.is_participant()]
    service = authenticate_service_account()
    
    log.debug("tournaments_report: Updating")
    sync_sheet_table(service, "Attendee Status", sheet_header, sheet_data, 1, "Tournaments", secret("folder_id"))


