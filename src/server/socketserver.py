import socket
import threading
import random
import json

from log.logger import log
from util.secrets import secret
from model.notification_manager import NotificationManager

class SocketServer:
  _instance = None
  
  @classmethod
  def shared(cls):
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance
  
  def __init__(self, psk=None, interface=None, port=None):
    self.interface = interface or secret("socket_interface", "127.0.0.1")
    self.port = port or secret("socket_port", 8081)
    self.psk = psk or secret("socket_psk", "")
    self.clients = []
    self.last_broadcast = None

    def received_notification(key, notification):
      if key != "event":
        return
      
      event = notification.get("event")
      num_scanned = event.num_scanned_attendees()
      num_eligible_attendees = event.num_eligible_attendees()

      self.broadcast(
        {
          'type': 'event',
          'data': {
            'event': {
              'name': event.name if hasattr(event, 'name') else None,
              'total_attendees_scanned': num_scanned,
              'total_scannable': num_eligible_attendees,
            }
         }
        }
      )
    
    NotificationManager.shared().observe(received_notification)

  def broadcast(self, msg):
    json_str = json.dumps(msg)
    msg_raw = f"{len(json_str)}|{json_str}\n"
    self.last_broadcast = msg_raw

    log.debug(f"Broadcasting {len(msg_raw)} bytes to {len(self.clients)} socket clients: {msg}")
    for client in self.clients:
      client.send(msg_raw)

  def listen(self):
    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
      self.server_socket.bind((self.interface, self.port))
      self.server_socket.listen(5)  # Allow up to 5 queued connections
      log.info(f"Socket server listening on {self.interface}:{self.port}")
      
      # Create a thread for the listening loop
      self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
      self.listen_thread.start()
      
    except Exception as e:
      log.error(f"Socket server error: {e}")
      self.server_socket.close()
  
  def _listen_loop(self):
    try:
      while True:
        client_socket, client_address = self.server_socket.accept()
        client_ip, client_port = client_address
        log.debug(f"New connection from {client_ip}:{client_port}; {len(self.clients)+1} clients total")

        client = SocketClient(self, client_socket, client_ip, client_port)
        if self.last_broadcast is not None:
          client.send(self.last_broadcast)
        self.clients.append(client)
        
    except Exception as exc:
      log.error(f"Socket server loop error", exception=exc)
    finally:
      self.server_socket.close()

  def disconnected(self, client):
    if client in self.clients:
      self.clients.remove(client)
      log.debug(f"Client {client.ip}:{client.port} disconnected; {len(self.clients)} clients remaining")

class SocketClient:
  def __init__(self, server, client_socket, client_ip, client_port):
    self.socket = client_socket
    self.ip = client_ip
    self.port = client_port
    self.server = server

    self._server_rand = random.getrandbits(128)
  
  def send(self, msg):
    try:
      self.socket.sendall(msg.encode('utf-8'))
    except (BrokenPipeError, ConnectionResetError, socket.error) as exc:
      log.debug(f"Client at {self.ip} seems disconnected; removing", exception=exc)
      try:
        self.socket.close()
      except:
        pass
      self.server.disconnected(self)
    except Exception as exc:
      log.warn(f"Error sending message to client at {self.ip}; removing", exception=exc)
      try:
        self.socket.close()
      except:
        pass
      self.server.disconnected(self)
