def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if attendee.info()["rank_comments"] is not None:
    return { "msg": f"Rank comment: {attendee.info()["rank_comments"]}", "code": "8a" }
  return None
