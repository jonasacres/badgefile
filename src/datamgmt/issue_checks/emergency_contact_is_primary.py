
import re

def run_check(attendee):
  for check in [ check_name, check_phone ]:
    result = check(attendee)
    if result is not None:
      return result
  return None
  
def check_name(attendee):
  primary_info = attendee.primary().info()
  match_names = [
    f"{primary_info['name_given']} {primary_info['name_family']}".lower(),
    f"{primary_info['name_family']} {primary_info['name_given']}".lower(),
    f"{primary_info['name_given']} {primary_info['name_mi']} {primary_info['name_family']}".lower(),
    f"{primary_info['name_family']} {primary_info['name_given']} {primary_info['name_mi']}".lower(),
  ]

  if attendee.info()['emergency_contact_name'].lower() in match_names:
    return {
      "msg": "Attendee emergency contact matches primary attendee name",
      "match_type": "name",
      "primary_id": primary_info["badgefile_id"]
    }
  
  return None

def check_phone(attendee):
  pri_info = attendee.primary().info()
  att_phone = standardize_phone(attendee.info()["emergency_contact_phone"])

  phone_fields = [ "phone_mobile", "phone_cell", "phone_a" ]
  for field in phone_fields:
    if pri_info[field] == None:
      continue
    pri_phone = standardize_phone(pri_info[field])
    if att_phone == pri_phone:
      return {
        "msg": "Attendee emergency contact matches primary registrant phone",
        "match_type": "phone",
        "primary_id": attendee.primary().id(),
      }
  return None


def standardize_phone(phone_num):
  """
  Formats a valid US phone number to '123-456-7890'.
  If the phone number is not valid or not US-based, returns the original string.
  """
  # Remove all non-digit characters
  digits = re.sub(r"\D", "", phone_num)
  
  # Check if it's a valid US number (10 digits or 11 digits with a leading 1)
  if len(digits) == 11 and digits.startswith("1"):
      digits = digits[1:]  # Strip the leading 1 for formatting
  elif len(digits) != 10:
      return phone_num  # Return the original if not a valid US number

  # Format as '123-456-7890'
  formatted_number = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
  return formatted_number
