def run_check(attendee):
  # this issue should show for anyone who doesn't have housing + hasn't said they're staying off-campus
  if attendee.party_housing():
    return None # attendee has housing, so we're good
  if attendee.will_arrange_own_housing() or attendee.primary().will_arrange_own_housing():
    return None # attendee party is arranging their own housing
  
  # we don't know for sure they have housing, so this is an issue
  return {"msg": f"Attendee has not booked housing or indicated off-campus arrangements", "category": 'housing', "code": "3e"}
  
