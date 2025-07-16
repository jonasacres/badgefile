import time
from datetime import datetime

from log.logger import log
from util.secrets import secret
from integrations.leago import Leago
from model.notification_manager import NotificationManager

class LeagoWatcher:
  def __init__(self):
    self.leago = Leago("https://api.leago.gg", "https://id.leago.gg", secret("leago_event_key"))
    self.dirty = {}
    self.last_refresh = None

  def run(self):
    self.leago.login()
    import threading
    
    def background_thread():
      log.info("Starting LeagoWatcher background thread")
      last_data = None
      while True:
        try:
          time.sleep(0.1)
          new_data = self.current_stats()
          if new_data != last_data:
            last_data = new_data
            log.debug(f"Broadcasting tournament update: {new_data['tournament_name']} {new_data['in_progress']}/{new_data['total_matches']}")
            NotificationManager.shared().notify("tournament_data", {"tournament_data":last_data})
        except Exception as exc:
          log.error("Error in LeagoWatcher background thread", exception=exc)
          time.sleep(10)
    
    thread = threading.Thread(target=background_thread, daemon=True)
    thread.start()

 
  def current_tournament(self):
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H%M")
    
    # Check if it's 2025-07-16
    if current_date == "2025-07-16":
      return "diehard"
    
    # For other dates, check time ranges
    time_int = int(current_time)
    
    if 0 <= time_int <= 1245:
      return "open"
    elif 1245 < time_int <= 1445:
      return "seniors"
    elif 1445 < time_int <= 1800:
      return "womens"
    else:
      return None
  
  def current_round(self, tournament):
    now = datetime.now()
    current_date = now.strftime("%m-%d")
    
    # If tournament is "diehard", return round 1
    if tournament == "diehard":
      current_time = now.strftime("%H%M")
      time_int = int(current_time)
      
      if time_int < 1100:
        return 1
      elif time_int <= 1330:
        return 2
      elif time_int <= 1530:
        return 3
      else:
        return 4
      return 1
    
    # For other tournaments, check the date
    if current_date == "07-13":
      return 1
    elif current_date == "07-14":
      return 2
    elif current_date == "07-15":
      return 3
    elif current_date == "07-17":
      return 4
    elif current_date == "07-18":
      return 5
    elif current_date == "07-19":
      return 6
    elif current_date == "07-20":
      return 7
    else:
      return None
  
  def current_stats(self, tournament_name=None):
    blank_result = { "tournament_name": None, "total_matches": 0, "completed": 0, "in_progress": 0 }
    if not tournament_name:
      tournament_name = self.current_tournament()
    if not tournament_name:
      return blank_result
    
    current_round = self.current_round(tournament_name)
    tournament = self.leago.tournament_by_badgefile_name(tournament_name)

    if not tournament:
      return blank_result

    matches = self.leago.get_matches(tournament['key'], current_round)
    num_matches = len(matches)
    num_completed = len([match for match in matches if match["players"][0]["outcome"] != 0])
    num_in_progress = num_matches - num_completed

    return {
      "tournament_name": tournament_name,
      "total_matches": num_matches,
      "completed": num_completed,
      "in_progress": num_in_progress,
    }
