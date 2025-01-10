def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  tournaments = attendee.tournaments()
  if "open" in tournaments and "masters" in tournaments:
    return { "msg": "Enrolled in both Masters and US Open" }
  return None