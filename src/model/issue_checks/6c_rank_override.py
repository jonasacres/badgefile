def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if attendee.rating_override_requested():
    return { "msg": "Rank override requested", "category": 'tournament', "code": "6c" }
  return None
