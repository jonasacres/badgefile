def run_check(attendee):
  tournaments = attendee.tournaments()
  if len(tournaments) > 0 and not attendee.is_participant():
    return { "msg": f"Enrolled in tournaments as non-participant ({', '.join(tournaments)})" }
  return None
