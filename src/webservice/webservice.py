import json
import os
import re
import base64
from flask import Flask, request, redirect, render_template, jsonify, abort
from flask_sock import Sock
from werkzeug.exceptions import NotFound

from log.logger import log
from util.version import Version
from util.secrets import secret
from model.event import Event, AttendeeNotEligible


class HTTPError(Exception):
  def __init__(self, status, message=None, data=None):
    self.status = status
    self.message = message
    self.data = data
    super().__init__(self.message)

class WebService:
  def __init__(self, badgefile, listen_interface='127.0.0.1', port=8080):
    self.badgefile = badgefile
    self.listen_interface = listen_interface
    self.port = port
    template_dir = os.path.abspath('src/static/html_templates')
    self.app = Flask(__name__, template_folder=template_dir)
    self.sock = Sock(self.app)
    self.websocket_clients = set()
    self._setup_routes()

  def ip():    
    client_ip = request.remote_addr
    
    # Check if client_ip is RFC 1918 (private) or localhost
    is_private = (
      client_ip.startswith('10.') or
      client_ip.startswith('172.16.') or
      client_ip.startswith('172.17.') or
      client_ip.startswith('172.18.') or
      client_ip.startswith('172.19.') or
      client_ip.startswith('172.2') or
      client_ip.startswith('172.30.') or
      client_ip.startswith('172.31.') or
      client_ip.startswith('192.168.') or
      client_ip.startswith('127.')
    )
    
    # Check if X-Real-Ip header exists and is valid-ish
    x_real_ip = request.headers.get('X-Real-Ip')
    log.debug(f"client_ip: {client_ip}, is_private: {is_private}, x_real_ip: {x_real_ip}, headers: {request.headers}")
    
    if is_private and x_real_ip:
      return x_real_ip
    else:
      return client_ip

  def logmsg(self, msg):
    client_ip = WebService.ip()
    method = request.method
    endpoint = request.path
    return f"{client_ip} {method} {endpoint}: {msg}"
  
  def require_authentication(self):
    # Check for HTTP Basic Authentication
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Basic '):
      # Extract and decode credentials
      encoded_credentials = auth_header[6:]  # Remove 'Basic ' prefix
      try:
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        username, password = decoded_credentials.split(':', 1)
        credentials_valid = False # TODO: implement a user list
        if credentials_valid:
          log.debug(self.logmsg("Authenticated"))
          return  # Authentication successful
        else:
          log.info(self.logmsg(f"Invalid credentials for user '{username}'"))
      except Exception:
        log.info(self.logmsg("Invalid credentials"))
        pass  # Continue to authentication failure
    
    # Check for HTTP Bearer Authentication
    elif auth_header and auth_header.startswith('Bearer '):
      token = auth_header[7:]  # Remove 'Bearer ' prefix
      if token == secret("web_apikey"):
        log.debug(self.logmsg("Authenticated"))
        return  # Authentication successful
      else:
        token_preview = f"'{token[0:8]}'..." if len(token) > 8 else f"'{token}'"
        log.info(self.logmsg(f"Invalid bearer token {token_preview}"))
    else:
      log.debug(self.logmsg("No credentials"))
    
    # Authentication failed or no authentication provided
    self.fail_request(401, "Authentication required")
  
  def parse_request(self):
    try:
      # Try to parse JSON regardless of Content-Type header
      data = request.get_json(force=True, silent=True)
      
      # If parsing failed or didn't return a dict, try to read the raw data
      if data is None:
        data = json.loads(request.data.decode('utf-8')) if request.data else {}
      
      if not isinstance(data, dict):
        self.fail_request(400, "Request body must be a JSON object")
    except json.JSONDecodeError:
      self.fail_request(400, "Invalid JSON in request body")
    
    return data
  
  def fail_request(self, status, message=None, data=None):
    response = jsonify({
      "status": status,
      "error": {
        "message": message,
        "data": data,
      }
    })

    response.status_code = status
    raise HTTPError(status, message, data)

  def respond(self, response_obj, status=200):
    wrapped_response = jsonify({
      "status": status,
      "response": response_obj,
    })

    wrapped_response.status_code = status
    wrapped_response.mimetype = 'application/json'
    abort(wrapped_response)
  
  def handler_crashed(self, exc):
    log.error(self.logmsg(f"Handler crashed: {str(exc)}"), exception=exc)
    response = jsonify({
      "status": 500,
      "error": {
        "message": "Internal error"
      }
    })
    response.status_code = 500
    return response

  def broadcast_to_websockets(self, message):
    closed_sockets = set()
    for ws in self.websocket_clients:
      try:
        ws.send(json.dumps(message))
      except Exception as exc:
        log.warn(f"Failed to send to websocket", exception=exc)
        closed_sockets.add(ws)
    
    # Remove closed websockets
    self.websocket_clients -= closed_sockets

  def _setup_routes(self):
    # Add a decorator to measure request processing time and log metrics
    @self.app.after_request
    def log_request_info(response):
      # Calculate request processing time (need to store start time in g)
      from flask import g
      import time
      from datetime import datetime
      
      # Get request processing time if available
      if hasattr(g, 'start_time'):
        process_time = (time.time() - g.start_time) * 1000  # Convert to ms
      else:
        process_time = 0
        
      # Get request and response sizes
      request_size = request.content_length or 0
      response_size = response.calculate_content_length() or 0
      
      # Format timestamp
      timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
      
      # Log the request metrics
      log.debug(f"{WebService.ip()} - {timestamp} \"{request.method} {request.path}\" {response.status_code} {process_time:.0f}ms {request_size} {response_size}")
      
      return response
      
    @self.app.before_request
    def record_request_start_time():
      from flask import g
      import time
      g.start_time = time.time()
    
    @self.app.errorhandler(Exception)
    def handle_exception(exc):
      if isinstance(exc, HTTPError):
        # This is an intentional abort with a specific status code
        response = jsonify({
          "status": exc.status,
          "error": {
            "message": exc.message,
            "data": exc.data,
          }
        })
        response.status_code = exc.status
        return response
      elif isinstance(exc, NotFound):
        # Handle 404 Not Found errors
        response = jsonify({
          "status": 404,
          "error": {
            "message": str(exc) or "Resource not found",
            "data": None,
          }
        })
        response.status_code = 404
        return response
      else:
        # This is an unexpected exception
        return self.handler_crashed(exc)
    
    @self.app.route('/')
    def home():
      return redirect('https://www.gocongress.org/')
    
    @self.app.route('/version')
    def version():
      return jsonify({'version': Version().hash()})
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['GET'])
    def confirm_housing_get(hashid):
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      if not attendee.is_primary():
        self.fail_request(400, "Only primary registrants can confirm housing")
      
      if attendee.party_housing():
        return render_template('confirm_housing_already_have.html', 
                              attendee=attendee.info(),
                              message="You have already reserved housing. Thank you for registering for the 2025 US Go Congress.")
      
      return render_template('confirm_housing.html', 
                            attendee=attendee.info(),
                            will_arrange_own_housing=attendee.will_arrange_own_housing())
    
    @self.app.route('/attendees/<hashid>/confirm_housing', methods=['POST'])
    def confirm_housing_post(hashid):
      attendee = self.badgefile.lookup_attendee_by_hash_id(hashid)
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      if not attendee.is_primary():
        self.fail_request(400, "Only primary registrants can confirm housing")
      
      will_arrange_own_housing = request.form.get('will_arrange_own_housing')
      if will_arrange_own_housing not in ['true', 'false']:
        self.fail_request(400, "Invalid housing preference")
      
      attendee.set_will_arrange_own_housing(will_arrange_own_housing == 'true')
      return render_template('confirm_housing_thank_you.html', 
                            attendee=attendee.info(),
                            message="Thank you for responding to our housing survey.")
    
    @self.sock.route('/ws')
    def monitor(ws):
      self.require_authentication()
      self.websocket_clients.add(ws)
      log.info(self.logmsg(f"WebSocket client connected, total clients: {len(self.websocket_clients)}"))
      try:
        # Keep the connection alive until client disconnects
        while True:
          # This will block until a message is received or the connection is closed
          message = ws.receive()
          # We're not expecting any messages from the client, but we could process them here
      except Exception as exc:
        log.info(self.logmsg(f"WebSocket disconnected"), exception=exc)
      finally:
        self.websocket_clients.discard(ws)
        log.info(self.logmsg(f"WebSocket client disconnected, remaining clients: {len(self.websocket_clients)}"))

    @self.app.route('/events/<event_name>/scans', methods=['POST'])
    def attendee_scans_post(event_name):
      self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      request = self.parse_request()

      if 'badgefile_id' in request:
        attendee = self.badgefile.lookup_attendee(request['badgefile_id'])
      elif 'hash_id' in request:
        attendee = self.badgefile.lookup_attendee_by_hash_id(request['hash_id'])
      else:
        self.fail_request(400, "Missing badgefile_id or hash_id in request")

      is_reset = request.get('reset', False) == True
      
      if attendee is None:
        self.fail_request(404, "Attendee not found")
      
      event = Event(event_name)
      try:
        num_scans = event.scan_in_attendee(attendee, is_reset=is_reset)
      except AttendeeNotEligible:
        self.fail_request(400, "Attendee not eligible", {"attendee": attendee.web_info()})
      
      total_scans_for_event = event.num_scanned_attendees()
      total_eligible = event.num_eligible_attendees()

      response_data = {
        "attendee": attendee.web_info(),
        "event": {
          "name": event_name,
          "is_reset": is_reset,
          "num_scans_for_attendee": num_scans,
          "total_attendees_scanned": total_scans_for_event,
          "total_scannable": total_eligible,
        }
      }

      # Broadcast scan event to all connected websocket clients
      websocket_message = {
        "type": "scan", 
        "data": response_data,
      }
      self.broadcast_to_websockets(websocket_message)

      self.respond(response_data)

    @self.app.route('/events/<event_name>/scans', methods=['GET'])
    def attendee_scans_get(event_name):
      self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      event = Event(event_name)

      self.respond({
        "event": {
          "name": event_name,
          "scans": event.scan_counts(),
        }
      })
    
    @self.app.route('/events/<event_name>/status', methods=['GET'])
    def attendee_status_get(event_name):
      self.require_authentication()

      if not Event.exists(event_name):
        self.fail_request(404, "Event not found")
      
      event = Event(event_name)
      total_scans_for_event = event.num_scanned_attendees()
      total_eligible = event.num_eligible_attendees()

      self.respond({
        "event": {
          "name": event_name,
          "total_attendees_scanned": total_scans_for_event,
          "total_scannable": total_eligible,
        }
      })

  def run(self):
    self.app.run(host=self.listen_interface, port=self.port)
