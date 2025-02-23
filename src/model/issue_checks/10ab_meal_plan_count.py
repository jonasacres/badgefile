from datetime import datetime

def run_check(attendee):
  if not attendee.is_primary():
    return None
  
  if not attendee.party_meal_plan():
    return None
  
  num_meal_plans = attendee.party_meal_plan().num_meal_plans()
  party_size = len(attendee.party())

  if num_meal_plans > party_size:
    return {"msg": f"Party has {num_meal_plans} mean plans, but only {party_size} members", "category": "mealplan", "code": "10b"}
  if num_meal_plans != 0 and num_meal_plans != party_size:
    return {"msg": f"Only some party members have meal plans; must ask which", "category": "mealplan", "code": "10a"}
  
  return None
