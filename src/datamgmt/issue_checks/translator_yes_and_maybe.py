from datetime import datetime

def run_check(attendee):
  info = attendee.info()
  options = str(info['translator']).split(",")
  if len(options) > 1:
    return {'msg': f"Selected multiple options for Translator: {', '.join(options)}", 'code': '8b'}
  return None