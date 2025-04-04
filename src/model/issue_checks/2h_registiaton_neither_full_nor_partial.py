def run_check(attendee):
  if attendee.is_cancelled():
    return None
  if attendee.is_partial_week() or attendee.is_full_week():
    return None
  
  return {"msg": "Has neither full NOR partial registration", "category": 'registration', "code": "2h"}
