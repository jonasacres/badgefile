def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  if not "masters" in attendee.tournaments():
    return None
  
  if attendee.effective_rank() is None:
    return {'msg': f"Requests Masters, but no rating on file", 'code': '5c', 'category': 'tournament'}
  if attendee.effective_rank() < 5.0:
    return {'msg': f"Requests Masters, but rating is {attendee.effective_rank()}", 'category': 'tournament', 'code': '5c'}
  return None