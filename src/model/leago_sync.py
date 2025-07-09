import time

from log.logger import log
from util.secrets import secret
from integrations.leago import Leago
from model.notification_manager import NotificationManager

class LeagoSync:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    self.leago = Leago("https://api.leago.gg", "https://id.leago.gg", secret("leago_event_key"))
    self.dirty = {}
    self.last_refresh = None
  
  def run(self):
    import threading

    def sync_thread_outer():
      self.sync_thread_body()

    self.watch_for_changes()
    thread = threading.Thread(target=sync_thread_outer, daemon=True)
    thread.start()

  def watch_for_changes(self):
    def received_notification(key, notification):
      attendee = notification.get("attendee")

      if attendee:
        log.info(f"Pushing change to {attendee.full_name()} {attendee.id()} to Leago")
        self.mark_dirty(attendee)
    
    NotificationManager.shared().observe(received_notification)

  def mark_dirty(self, attendee):
    self.dirty[attendee.id()] = attendee
  
  def sync_all(self):
    self.last_refresh = None
    self.leago.login()
  
  def sync(self, attendee):
    try:
      self.leago.sync_attendee_info(attendee)
      self.leago.sync_attendee_enrollment(attendee)

      if attendee.is_checked_in():
        self.leago.checkin_attendee(attendee)
      else:
        self.leago.checkout_attendee(attendee)
      return True
    except Exception as exc:
      log.warn(f"Caught exception synchronizing {attendee.full_name()} {attendee.id()} to leago", exception=exc)
      return False
    
  def force_refresh(self):
    log.info(f"Refreshing Leago data")
    try:
      self.leago.get_registrations(force=True)
      tournaments = self.leago.get_tournaments(force=True)
      for tournament_name, tournament in tournaments.items():
        self.leago.get_tournament_players(tournament, force=True)

      participants = [attendee for attendee in self.badgefile.attendees() if attendee.is_participant() and str(attendee.badge_rating()) != '']
      for attendee in participants:
        self.mark_dirty(attendee)

      self.last_refresh = time.time()
      log.info(f"Leago data refreshed.")
      return True
    except Exception as exc:
      log.error(f"LeagoSync force_refresh encountered exception", exception=exc)
      return False
  
  def sync_thread_body(self):
    base_backoff = 0.1
    max_backoff = 30.0
    backoff = base_backoff

    leago_refresh_interval = 5*60

    log.info("Starting LeagoSync client")

    while True:
      try:
        if self.last_refresh is None or (time.time() - self.last_refresh) > leago_refresh_interval:
          if not self.force_refresh():
            backoff = max([max_backoff, 2*backoff])
            log.debug(f"Refresh of Leago registrations failed; new backoff interval is {backoff}")
            time.sleep(backoff)
        
        if len(self.dirty) == 0:
          time.sleep(0.1)
          continue

        attendee = next(iter(self.dirty.values()))
        log.debug(f"Syncing attendee {attendee.full_name()} {attendee.id()} to Leago; have {len(self.dirty)} to sync")

        if self.sync(attendee):
          backoff = base_backoff
          del self.dirty[attendee.id()]
          log.debug(f"Sync of attendee {attendee.full_name()} {attendee.id()} to Leago succeeded; have {len(self.dirty)} to sync")
        else:
          backoff = max([max_backoff, 2*backoff])
          log.debug(f"Sync of attendee {attendee.full_name()} {attendee.id()} to Leago failed; have {len(self.dirty)} to sync. New backoff interval: {backoff}")
          time.sleep(backoff)
      except Exception as exc:
        log.error(f"LeagoSync thread loop encountered exception", exception=exc)
      
