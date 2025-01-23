import re
import subprocess
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
  
def git_revision():
  try:
    return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
  except Exception:
    return None

def git_branch():
  try:
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
  except Exception:
    return None

def git_has_changes():
  try:
    return subprocess.check_output(["git", "status", "--porcelain"]).decode().strip() != ""
  except Exception:
    return False

def git_summary():
  try:
    subprocess.check_output(["git", "--version"])
  except (subprocess.CalledProcessError, FileNotFoundError):
    return "no git client on host"
  
  try:
    subprocess.check_output(["git", "rev-parse", "--git-dir"], stderr=subprocess.DEVNULL)
  except subprocess.CalledProcessError:
    return "no git repo in working directory"
  
  change_star = "*" if git_has_changes() else ""
  return f"{git_branch()} ({git_revision()}{change_star})"
