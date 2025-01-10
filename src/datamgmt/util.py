import re

class util:
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

