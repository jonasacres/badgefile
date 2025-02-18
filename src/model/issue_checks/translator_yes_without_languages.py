from datetime import datetime

def run_check(attendee):
  info = attendee.info()
  if 'Yes' in str(info['translator']) and info['languages'] == None:
    return {'msg': f"Volunteered to translate, but did not indicate languages", 'category': 'translation', 'code': '8a'}
  return None