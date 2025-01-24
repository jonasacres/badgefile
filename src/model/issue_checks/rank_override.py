def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if attendee.info()["rank_playing"].lower() not in ["use aga rank", "not playing in any tournaments"]:
    return { "msg": "Rank override requested", "code": "6c" }
  return None
