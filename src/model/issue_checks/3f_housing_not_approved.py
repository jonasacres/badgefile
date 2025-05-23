def run_check(attendee):
  # this issue should show for anyone who registered for housing but isn't approved yet

  if not attendee.party_housing():
    return None # attendee does not have housing; non-issue
  if attendee.is_housing_approved():
    return None # attendee housing is approved; non-issue
  
  # housing but no approval; this is an issue
  return {"msg": f"Attendee has a housing registration pending approval", "category": 'housing', "code": "3f"}
  
