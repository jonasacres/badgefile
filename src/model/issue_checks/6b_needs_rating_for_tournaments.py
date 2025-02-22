def run_check(attendee):
  if not attendee.is_participant():
    return None
  
  indicated_not_playing_on_rank = attendee.info()["rank_playing"].lower() == "not playing in any tournaments"
  playing_in_tournaments = len(attendee.tournaments()) > 0
  if indicated_not_playing_on_rank and playing_in_tournaments:
    return { "msg": f": Chose 'not playing in any tournaments' for rank, but also selected at least one tournament to play in", "category": 'tournament', "code": "6b" }
  return None
