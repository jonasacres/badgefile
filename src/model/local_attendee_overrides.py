import yaml
import os

class LocalAttendeeOverrides:
  _instance = None

  @classmethod
  def shared(cls):
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance

  def __init__(self):
    self.path = "local_attendee_overrides.yaml"
    self.data = self.process_yaml()

  def process_yaml(self):
    if not os.path.exists(self.path):
      return {}

    with open(self.path, "r", encoding="utf-8") as f:
      data = yaml.safe_load(f)

    if not isinstance(data, dict):
      return {}

    return data
  
  def apply_overrides(self, attendee_info):
    badgefile_id = attendee_info.get('badgefile_id')
    if badgefile_id is None:
      return attendee_info
    
    override_data = self.data.get(badgefile_id, {})
    merged = attendee_info.copy()
    merged.update(override_data)
    return merged
  
  def set_override(self, attendee, override_info):
    base_info = attendee.final_info(apply_local_overrides=False)

    if 'languages' in override_info:
      supported_languages = ['korean', 'chinese', 'japanese', 'spanish']

      override_info = override_info.copy()
      for lang in supported_languages:
        speaks_language = lang in override_info['languages']
        override_info['override_speaks_' + lang] = 'yes' if speaks_language else 'no'
      
      del override_info['languages']
    
    diff = {}
    for key in override_info:
      base_value = base_info.get(key)
      override_value = override_info[key]
      
      # Include the override if the value is different from base, or if the key doesn't exist in base
      if base_value != override_value:
        diff[key] = override_value

    self.data[attendee.id()] = diff
    with open(self.path, "w", encoding="utf-8") as f:
      yaml.safe_dump(self.data, f, allow_unicode=True, sort_keys=True)

    return diff
