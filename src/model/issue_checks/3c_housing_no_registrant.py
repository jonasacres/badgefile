def run_check(attendee):
  has_housing = any(activity.is_housing() for activity in attendee.activities())
  has_registration = attendee.primary() is not None
  
  if has_housing and not has_registration:
    return {"msg": f"Has housing, but no Congress registration", "category": "housing", "code": "3c" }
  return None
