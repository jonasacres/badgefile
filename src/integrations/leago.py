import os
import json
import time
import hashlib
import base64
import secrets
import re
import requests
from urllib.parse import urlencode, parse_qs, urlparse

from log.logger import log
from util.secrets import secret

def decode_jwt_payload(jwt_token):
    """Decode and return the payload of a JWT token for debugging"""
    try:
        # Split the JWT into parts
        parts = jwt_token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode the payload (second part)
        payload_b64 = parts[1]
        # Add padding if needed
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        
        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        return payload
    except Exception as e:
        log.warn(f"Failed to decode JWT: {e}")
        return None

class Leago:
  def __init__(self, url, id_url, event_key):
    self.leago_url = url
    self.leago_id_url = id_url
    self.event_key = event_key
    self.tournaments = None
    self.tournaments_by_name = None
    self.tournament_players = {}
    self.registrations = None
    self.token_file = "leago_token.json"
    self._token_data = None
    self.state = secrets.token_hex(32)
    self._session = None  # Store authenticated session
    self.matches = {}
    
    # OAuth2 configuration
    self.client_id = secret('leago_client_id', "Leago.WebClient")
    self.client_secret = secret('leago_client_secret', 'foobar')
    self.user_email = secret('leago_user_email')
    self.user_password = secret('leago_user_password')

    self.redirect_uri = secret('leago_redirect_uri', 'https://leago.gg/auth/signin-callback')
    self.auth_url = f"{self.leago_id_url}/connect/authorize"
    self.token_url = f"{self.leago_id_url}/connect/token"
  
  def _authenticate_session(self, session):
    """Authenticate a session with cookies for OAuth2 flow"""
    # Step 1: Get the signin page to obtain __RequestVerificationToken and cookies
    signin_url = f"{self.leago_id_url}/signin?returnUrl=https%3A%2F%2Fleago.gg%2F"
    log.debug(f"Getting signin page: {signin_url}")
    
    response = session.get(signin_url)
    response.raise_for_status()
    
    # Extract __RequestVerificationToken from the HTML response
    token_match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', response.text)
    if not token_match:
      raise Exception("Could not find __RequestVerificationToken in signin page")
    
    request_verification_token = token_match.group(1)
    log.debug("Extracted __RequestVerificationToken")
    
    # Step 2: Submit login credentials to get authenticated cookies
    login_data = {
      'Input.Email': self.user_email,
      'Input.Password': self.user_password,
      '__RequestVerificationToken': request_verification_token,
      'Input.RememberMe': 'false'
    }
    
    log.debug("Submitting login credentials")
    response = session.post(signin_url, data=login_data)
    response.raise_for_status()
    
    # Check if login was successful (should redirect or show success)
    if response.status_code != 200 or "error" in response.text.lower():
      raise Exception("Login failed - check credentials")
    
    log.debug("Session authenticated successfully")
  
  def login(self):
    """Perform OAuth2 login flow with cookie-based authentication"""
    session = requests.Session()
    
    # Authenticate the session with cookies
    self._authenticate_session(session)
    
    # Step 3: Start OAuth2 authorization flow using authenticated session
    auth_url = self._get_authorization_url()
    log.debug(f"Making OAuth2 authorization request: {auth_url}")
    
    response = session.get(auth_url, allow_redirects=False)
    log.debug(f"Authorization response status: {response.status_code}")
    
    if response.status_code != 302:
      raise Exception(f"Expected 302 redirect, got {response.status_code}")
    
    if 'Location' not in response.headers:
      raise Exception("No Location header in authorization response")
    
    # Step 4: Extract authorization code from redirect URL
    redirect_url = response.headers['Location']
    log.debug(f"Authorization redirect URL: {redirect_url}")
    
    parsed_url = urlparse(redirect_url)
    query_params = parse_qs(parsed_url.query)
    
    if 'error' in query_params:
      error = query_params['error'][0]
      error_description = query_params.get('error_description', [''])[0]
      raise Exception(f"OAuth2 authorization failed: {error} - {error_description}")
    
    if 'code' not in query_params:
      raise Exception("No authorization code found in redirect URL")
    
    authorization_code = query_params['code'][0]
    log.debug("Got authorization code, exchanging for tokens")
    
    # Step 5: Exchange authorization code for access token
    token_data = self._exchange_code_for_token(authorization_code)
    
    # Save the authenticated session for reuse in token refresh
    self._session = session
    
    log.info("Leago login completed successfully")
    return token_data['token']['access_token']

  def _load_token(self):
    """Load token from file if it exists and is valid"""

    # we probably don't want to memoize this, because we have a combination of daemon+manual scripts
    # (though this leaves a troubling race condition where two processes could try to refresh simultaneously)

    # memoization:
    # if self._token_data is not None:
    #   return self._token_data
      
    if not os.path.exists(self.token_file):
      return None
      
    try:
      with open(self.token_file, 'r') as f:
        self._token_data = json.load(f)
      
      # Always return the token data, even if expired, so refresh tokens can be accessed
      return self._token_data
    except Exception as e:
      log.warn(f"Failed to load Leago token: {e}")
      return None
  
  def _save_token(self, token_data):
    """Save token to file"""
    try:
      with open(self.token_file, 'w') as f:
        json.dump(token_data, f, indent=2)
      self._token_data = token_data
      log.debug("Leago token saved successfully")
    except Exception as e:
      log.warn(f"Failed to save Leago token: {e}")
  
  def _generate_pkce_pair(self):
    """Generate PKCE code verifier and challenge"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
      hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge
  
  def _get_authorization_url(self):
    """Generate authorization URL for OAuth2 PKCE flow"""
    code_verifier, code_challenge = self._generate_pkce_pair()
    
    # Store code verifier for later use
    self._code_verifier = code_verifier
    
    params = {
      'client_id': self.client_id,
      'redirect_uri': self.redirect_uri,
      'response_type': 'code',
      'scope': 'Leago.WebAPI openid profile',
      'state': self.state,
      'code_challenge': code_challenge,
      'code_challenge_method': 'S256',
      'response_mode': 'query',
      'prompt': 'none',
    }
    
    return f"{self.auth_url}?{urlencode(params)}"
  
  def _exchange_code_for_token(self, authorization_code):
    """Exchange authorization code for access token"""
    data = {
      'client_id': self.client_id,
      'client_secret': self.client_secret,
      'grant_type': 'authorization_code',
      'code': authorization_code,
      'redirect_uri': self.redirect_uri,
      'code_verifier': self._code_verifier
    }
    
    headers = {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    response = requests.post(self.token_url, data=data, headers=headers)
    response.raise_for_status()
    
    token_response = response.json()
    
    # Calculate expiration time
    expires_at = time.time() + token_response.get('expires_in', 3600)
    token_response['expires_at'] = expires_at
    
    token_data = {
      'token': token_response,
      'client_id': self.client_id
    }
    
    # Save the id_token for refresh purposes
    if 'id_token' in token_response:
      token_data['id_token'] = token_response['id_token']
    
    self._save_token(token_data)
    return token_data

  def _refresh_token(self):
    """Refresh the access token using id_token_hint approach"""
    token_data = self._load_token()
    
    # Check for id_token in both possible locations (top level or nested in token)
    id_token = token_data.get('id_token') if token_data else None
    if not id_token and token_data and 'token' in token_data:
      id_token = token_data['token'].get('id_token')
    
    if not id_token:
      log.warn("No id_token available for refresh")
      return None
    
    log.debug("Starting token refresh using id_token_hint")
    
    # Generate new PKCE pair for the refresh request
    code_verifier, code_challenge = self._generate_pkce_pair()
    self._code_verifier = code_verifier
    self.state = secrets.token_hex(32)
    
    # Build the authorization URL with id_token_hint
    params = {
      'client_id': self.client_id,
      'redirect_uri': self.redirect_uri,
      'response_type': 'code',
      'scope': 'Leago.WebAPI openid profile',
      'state': self.state,
      'code_challenge': code_challenge,
      'code_challenge_method': 'S256',
      'response_mode': 'query',
      'prompt': 'none',
      'id_token_hint': id_token
    }
    
    auth_url = f"{self.auth_url}?{urlencode(params)}"
    log.debug(f"Refresh auth URL: {auth_url}")
    
    try:
      # Use saved session if available, otherwise create a new one
      if self._session is None:
        log.debug("No saved session available, creating new session for refresh")
        self._session = requests.Session()
        # Re-authenticate the session
        self._authenticate_session(self._session)
      
      # Make the authorization request using the authenticated session
      response = self._session.get(auth_url, allow_redirects=False)
      log.debug(f"Refresh response status: {response.status_code}")
      
      if response.status_code == 302 and 'Location' in response.headers:
        redirect_url = response.headers['Location']
        log.debug(f"Refresh redirect URL: {redirect_url}")
        
        # Extract the authorization code from the redirect URL
        parsed_url = urlparse(redirect_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'error' in query_params:
          error = query_params['error'][0]
          error_description = query_params.get('error_description', [''])[0]
          log.warn(f"Token refresh failed: {error} - {error_description}")
          return None
        
        auth_code = query_params.get('code', [None])[0]
        if auth_code:
          log.debug("Got authorization code, exchanging for tokens")
          # Exchange the new authorization code for fresh tokens
          new_token_data = self._exchange_code_for_token(auth_code)
          log.info("Leago token refreshed successfully")
          return new_token_data
        else:
          log.warn("No authorization code in refresh response")
          return None
      else:
        log.warn(f"Unexpected response during token refresh: {response.status_code}")
        if response.text:
          log.debug(f"Response body: {response.text}")
        return None
        
    except Exception as exc:
      log.warn(f"Failed to refresh Leago token: {exc}", exception=exc)
      return None
  
  def get_access_token(self):
    """Get a valid access token, refreshing if necessary"""
    token_data = self._load_token()
    
    if not token_data:
      return None
    
    # Check if token needs refresh (within 5 minutes of expiry)
    if 'token' in token_data and 'expires_at' in token_data['token']:
      if time.time() > token_data['token']['expires_at']:
        log.debug("Leago token has expired")
        return None
      
      if time.time() > (token_data['token']['expires_at'] - 300):
        log.info("Leago token expiring soon, refreshing")
        refreshed_data = self._refresh_token()
        if refreshed_data:
          token_data = refreshed_data
        else:
          log.notice("Failed to refresh token, logging in again")
          self.login()
    
    return token_data['token']['access_token'] if token_data and 'token' in token_data else None
  
  def authenticate(self):
    """Start OAuth2 authentication flow"""
    auth_url = self._get_authorization_url()
    log.info(f"Please visit this URL to authenticate: {auth_url}")
    return auth_url
  
  def complete_authentication(self, redirect_url):
    """Complete OAuth2 authentication with the redirect URL"""
    parsed_url = urlparse(redirect_url)
    query_params = parse_qs(parsed_url.query)
    
    if 'error' in query_params:
      error = query_params['error'][0]
      error_description = query_params.get('error_description', [''])[0]
      raise Exception(f"OAuth2 error: {error} - {error_description}")
    
    if 'code' not in query_params:
      raise Exception("No authorization code found in redirect URL")
    
    authorization_code = query_params['code'][0]
    token_data = self._exchange_code_for_token(authorization_code)
    
    log.info("Leago authentication completed successfully")
    return token_data['token']['access_token']
  
  def deauthenticate(self):
    """Remove stored tokens"""
    if os.path.exists(self.token_file):
      os.remove(self.token_file)
    self._token_data = None
    self._session = None  # Clear saved session
    log.info("Leago tokens and session removed")
  
  def debug_token(self):
    """Debug method to inspect the current token and its JWT payload"""
    token_data = self._load_token()
    if not token_data:
      print("No token data available")
      return
    
    print("Current token data:")
    print(json.dumps(token_data, indent=2))
    
    # Check for id_token
    id_token = token_data.get('id_token')
    if not id_token and 'token' in token_data:
      id_token = token_data['token'].get('id_token')
    
    if id_token:
      print(f"\nID Token JWT: {id_token[:50]}...")
      payload = decode_jwt_payload(id_token)
      if payload:
        print("ID Token payload:")
        print(json.dumps(payload, indent=2))
    
    # Check for access_token
    if 'token' in token_data and 'access_token' in token_data['token']:
      access_token = token_data['token']['access_token']
      print(f"\nAccess Token JWT: {access_token[:50]}...")
      payload = decode_jwt_payload(access_token)
      if payload:
        print("Access Token payload:")
        print(json.dumps(payload, indent=2))
  
  def _get_auth_headers(self):
    """Get headers with valid access token"""
    token = self.get_access_token()
    if not token:
      try:
        self.login()
      except Exception as exc:
        log.warn("Caught exception authenticated to Leago", exception=exc)
        raise Exception("No valid access token available. Please authenticate first.")
    
    return {
      "Accept": "application/json",
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
    }
  
  def make_authenticated_request(self, method, url, **kwargs):
    """Make an authenticated request with automatic token refresh"""
    headers = self._get_auth_headers()
    if 'headers' in kwargs:
      headers.update(kwargs['headers'])
    kwargs['headers'] = headers
    
    response = requests.request(method, url, **kwargs)
    
    # If we get a 401, try to refresh the token and retry once
    if response.status_code == 401:
      log.info("Received 401, attempting token refresh")
      if self._refresh_token():
        headers = self._get_auth_headers()
        if 'headers' in kwargs:
          headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        response = requests.request(method, url, **kwargs)
    
    elif response.status_code // 100 != 2:
      log.warn(f"Leago {method} {url} returned HTTP {response.status_code}.\nPayload: {json.dumps(kwargs)}\nResponse: {response.text}")
    
    return response
  
  def get_matches(self, tournament_id, round_id, force=False):
    if tournament_id not in self.matches:
      self.matches[tournament_id] = {}
    
    is_expired = True
    if round_id in self.matches[tournament_id] and not force:
      last_check = self.matches[tournament_id][round_id]["last_check"]
      is_expired = time.time() - last_check >= 60
    
    if not is_expired:
      return self.matches[tournament_id][round_id]["matches"]

    url = f"{self.leago_url}/api/v1/tournaments/{tournament_id}/rounds/{round_id}/matches"
    response = self.make_authenticated_request('GET', url)
    response.raise_for_status()

    self.matches[tournament_id][round_id] = {
      "last_check": time.time(),
      "matches": response.json()
    }
    return response.json()
  
  def get_active_matches(self, tournament_id, round_id, force=False):
    matches = self.get_matches(tournament_id, round_id, force)
    return [match for match in matches if match["players"][0]["outcome"] != 0]
  
  def get_completed_matches(self, tournament_id, round_id, force=False):
    matches = self.get_matches(tournament_id, round_id, force)
    return [match for match in matches if match["players"][0]["outcome"] == 0]

  def get_tournaments(self, force=False):
    if self.tournaments is not None and not force:
      return self.tournaments
    
    url = f"{self.leago_url}/api/v1/events/{self.event_key}/tournaments"
    
    response = self.make_authenticated_request('GET', url)
    response.raise_for_status()

    self.tournaments = {}
    for tournament in response.json():
      self.tournaments[tournament.get('title').lower()] = tournament
    
    our_tournaments = ["open", "diehard", "masters", "womens", "seniors"]
    self.tournaments_by_name = {tourney_name: tournament for tourney_name in our_tournaments 
                               if (tournament := self.tournament_by_badgefile_name(tourney_name)) is not None}

    log.debug(f"Found tournaments: {self.tournaments_by_name.keys()}")
    return self.tournaments
  
  def tournament_by_badgefile_name(self, our_name):
    valid_titles = {
      "open": ["US Open", "2025 US Go Congress"],
      "seniors": ["Seniors Tournament"],
      "womens": ["Women's Tournament"],
      "diehard": ["Die Hard"],
      "masters": ["North American Masters", "Masters"]
    }

    # match on lowercase. this way, we can just copy-paste titles from leago and not worry.
    for key, titles in valid_titles.items():
      valid_titles[key] = [title.lower().strip() for title in titles]

    for title, tournament in self.get_tournaments().items():
      sanitized_title = title.lower().strip()
      if our_name in valid_titles and sanitized_title in valid_titles[our_name]:
        return tournament
    
    log.notice(f"Can't find tournament '{our_name}' in leago")
    return None
      
  
  def get_registrations(self, force=False):
    if self.registrations is not None and not force:
      return self.registrations
    
    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations"
    response = self.make_authenticated_request('GET', url)
    response.raise_for_status()

    self.registrations = {}
    for registration in response.json()['items']:
      self.registrations[registration.get('organizationMemberKey', 'none').lower()] = registration
    
    return self.registrations
  
  def get_tournament_players(self, tournament, force=False):
    if tournament['key'] in self.tournament_players and not force:
      return self.tournament_players[tournament['key']]
    
    self.tournament_players[tournament['key']] = []
    
    url = f"{self.leago_url}/api/v1/tournaments/{tournament['key']}/players"
    response = self.make_authenticated_request('GET', url)
    response.raise_for_status()

    for player_info in response.json():
      player_key = player_info['key']
      found_player = False

      if player_info['participationStatus'] != 1:
        continue

      for badgefile_id, reg in self.registrations.items():
        if reg['key'] == player_key:
          self.tournament_players[tournament['key']].append(badgefile_id)
          found_player = True
          break
      
      if not found_player:
        log.warn(f"Tournament {tournament['key']} ({tournament['title']}) has unrecognized player: {player_info['givenName']} {player_info['familyName']} {player_info['key']}")
    
    return self.tournament_players[tournament['key']]

  def tournament_for_name(self, tournament_name):
    return self.get_tournaments().get(tournament_name.lower(), None)

  def sync_attendee_info(self, attendee, force=False):
    registrations = self.get_registrations()
    id = str(attendee.id())

    if id in registrations:
      if not force:
        reg = registrations[id]
        payload = self.registration_payload_for_attendee(attendee)
        # Check if our local copy matches what's in leago
        differences = []
        for key in payload:
            local_value = payload.get(key)
            remote_value = reg.get(key)

            # when we supply values as "", they can come back as null/None. So force those to all be blank strings.

            if local_value is None:
              local_value = ""
            if remote_value is None:
              remote_value = ""
            if local_value != remote_value:
                differences.append(f"{key}: local='{local_value}' remote='{remote_value}'")
        
        if not differences:
            # our local copy matches what's in leago; don't waste a network operation unless forced
            return None
      self.update_attendee(attendee)
    else:
      self.register_attendee(attendee)
  
  def sync_attendee_enrollment(self, attendee, force=False):
    registrations = self.get_registrations()
    id = str(attendee.id())
    registration = registrations.get(id, None)

    if not registration:
      log.warn(f"Can't sync enrollment of attendee {attendee.full_name()} {attendee.id()}: not registered in Leago")
      return
    
    if self.tournaments_by_name is None:
      self.get_tournaments()

    player_tournaments = attendee.tournaments()

    if attendee.is_in_tournament('masters'):
      if not "masters" in player_tournaments:
        player_tournaments.append("masters")
      if "open" in player_tournaments:
        player_tournaments.remove("open")
    elif "masters" in player_tournaments:
      player_tournaments.remove("masters")

    log.debug(f"Attendee {attendee.full_name()} {attendee.id()} tournaments: {player_tournaments}")
    
    for tournament_name, tournament in  self.tournaments_by_name.items():
      is_participating = tournament_name in player_tournaments
      self.set_player_tournament_participation(attendee, tournament, is_participating, force)

  def registration_payload_for_attendee(self, attendee):
    info = attendee.final_info()
    id = str(attendee.id())

    # start by building the POST version (ie. registering someone into Leago who wasn't there before)
    payload = {
      "givenName": info['name_given'],
      "familyName": info['name_family'],
      "email": info['email'],
      "city": info['city'],
      "subnation": info['state'],
      "country": info['country'],
      "rankId": aga_badge_to_leago(info['badge_rating']),
      "rating": 0,
      "memberId": id,
      "clubName": info.get('aga_chapter') or "",
      "teamKey": "",
      "countryCode": "",
    }

    registrations = self.get_registrations()
    if id in registrations:
      # we already have this ID in the registration list, so do the PUT version
      reg = registrations[id]
      del payload["memberId"]
      del payload["rating"]
      del payload["teamKey"]
      del payload["countryCode"]
      payload["organizationMemberKey"] = id
      payload["key"] = reg["key"]
    return payload


  def register_attendee(self, attendee):
    log.error(f"We tried to register attendee {reg.get('key')} {reg.get('organizationMemberKey')}")
    return
  
    reg_payload = self.registration_payload_for_attendee(attendee)

    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations"
    
    response = self.make_authenticated_request('POST', url, json=reg_payload)
    response.raise_for_status()
    registration = response.json()
    self.get_registrations()[registration.get('organizationMemberKey').lower()] = registration

    return registration
  
  def unregister_attendee_by_reg(self, reg, force=False):
    log.error(f"We tried to unregistered attendee {reg.get('key')} {reg.get('organizationMemberKey')}")
    return
  
    if not force and not reg.get('organizationMemberKey') in self.get_registrations():
      return False
    
    log.info(f"Unregistering attendee {reg.get('organizationMemberKey')} {reg.get('key')} from Leago")
    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations/{reg.get('key')}"
    response = self.make_authenticated_request('DELETE', url)
    try:
      response.raise_for_status()
      member_key = reg.get('organizationMemberKey', '').lower()
      if member_key in self.get_registrations():
        del self.get_registrations()[member_key]
    except requests.exceptions.HTTPError as e:
      if e.response.status_code != 404:
        raise
    return True
  
  def set_player_tournament_participation(self, attendee, tournament, is_participating, force=False):
    log.error(f"We tried to set tournament enrollment for attendee {attendee.full_name()} {attendee.id()}")
    return
  
    log.debug(f"Setting player {attendee.full_name()} {attendee.id()} participating={is_participating} for tournament {tournament['key']} ({tournament['title']})")
    str_id = str(attendee.id())

    reg = self.get_registrations().get(str_id)
    if reg is None and force:
      reg = self.get_registrations(force=True).get(str_id)
    if reg is None:
      log.warn(f"Cannot set attendee {attendee.full_name()} {attendee.id()} participation={is_participating} for tournament {tournament['key']} ({tournament['title']}), as player does not seem to be in Leago")
      return False

    players = self.get_tournament_players(tournament)
    is_already_participating = str_id in players

    if is_participating != is_already_participating or force:
      url = f"{self.leago_url}/api/v1/tournaments/{tournament['key']}/participants/{reg['key']}"
      enrollment_payload = {'participating': is_participating}
      response = self.make_authenticated_request('PUT', url, json=enrollment_payload)
      response.raise_for_status()
    
    if is_participating and not is_already_participating:
      players.append(str_id)
    elif not is_participating and is_already_participating:
      players.remove(str_id)

  def checkin_attendee(self, attendee):
    self.update_attendee_checkin(attendee, 1)
  
  def checkout_attendee(self, attendee):
    self.update_attendee_checkin(attendee, 0)

  def update_attendee_checkin(self, attendee, status):
    registrations = self.get_registrations()
    id = str(attendee.id())
    reg = registrations[id]

    if reg.get('status') == status:
      log.debug(f"Attendee {attendee.full_name()} {attendee.id()} already has status {status} in Leago")
      return None # already matches what's in Leago
    
    log.debug(f"Attendee {attendee.full_name()} {attendee.id()} updating status to {status} in Leago")
    result = self.update_attendee(attendee, {'status': status})
    
    # if status == 1 and result:
    #   log.debug(f"Sending invite email via Leago to {attendee.full_name()} {attendee.id()}")
    #   self.send_invite_email(attendee)

    return result

  def send_invite_email(self, attendee):
    log.error(f"Tried to send Leago invite to attendee {attendee.full_name()} {attendee.id()}")
    return
  
    key = self.get_registrations()[str(attendee.id())]['key']
    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations/{key}/invite-email"
    self.make_authenticated_request('POST', url)

  def update_attendee(self, attendee, extra = {}):
    log.error(f"oh fuck we tried to update Leago: attendee {attendee.full_name()} {attendee.id()}, {extra}")
    return
  
    if not str(attendee.id()) in self.get_registrations():
      if not str(attendee.id()) in self.get_registrations(force=True):
        log.warn(f"Cannot update attendee {attendee.full_name()} (#{attendee.id()}) in Leago, since this member is not registered to event {self.event_key}")
        return None
      
    key = self.get_registrations()[str(attendee.id())]['key']

    reg_payload = self.registration_payload_for_attendee(attendee)
    reg_payload.update(extra)

    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations/{key}"
    
    response = self.make_authenticated_request('PUT', url, json=reg_payload)
    response.raise_for_status()
    registration = response.json()

    if str(attendee.id()) != str(registration.get('organizationMemberKey')):
      log.warn(f"Leago PUT /registrations response had organizationMemberKey {registration.get('organizationMemberKey', 'None')}; expected {attendee.id()}")
    self.get_registrations()[str(attendee.id())].update(registration)

    return registration

  def unregister_attendee(self, attendee):
    log.error(f"we tried to delete attendee {attendee.full_name()} {attendee.id()} from Leago")
    return
  
    id = str(attendee.id())
    registrations = self.get_registrations()
    if not id in registrations or not 'key' in registrations[id]:
      return False
    
    url = f"{self.leago_url}/api/v1/events/{self.event_key}/registrations/{registrations[id]['key']}"
    response = self.make_authenticated_request('DELETE', url)
    response.raise_for_status()
    del self.get_registrations()[id]
    return True

def aga_badge_to_leago(aga_badge_rank):
  rank = int(aga_badge_rank[0:-1])
  cls = aga_badge_rank[-1].lower()
  if cls == 'k':
    if rank > 30:
      rank = 30 # we have some 32k members. dunno why.
    return 30 - rank
  elif cls == 'd':
    return 30 + rank - 1
  elif cls == 'p':
    return 39 + rank - 1
  else:
    log.warn(f"Don't know how to convert rating {aga_badge_rank} to leago; treating as 30k / leago rank 0")
    return 0
  