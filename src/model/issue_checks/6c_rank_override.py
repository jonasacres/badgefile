def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if attendee.info()["rank_playing"].lower() not in ["use aga rank", "not playing in any tournaments"]:
    return { "msg": "Rank override requested", "category": 'membership', "code": "6c" }
  return None
