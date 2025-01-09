def run_check(attendee):
  if attendee.info()["rank_playing"].lower() not in ["use aga rank", "not playing in any tournaments"]:
    return { "msg": "Attendee wants to override AGA rank" }
  return None
