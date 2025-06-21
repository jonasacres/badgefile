import array
import wifi
import time
import ssl
import socketpool
import adafruit_requests
import json
import traceback

from rainbowio import colorwheel
import board
import displayio
import framebufferio
import rgbmatrix
import terminalio

WIFI_SSID = ""
WIFI_PASSWORD = ""
EVENT_NAME = "signtest"
BADGEFILE_URL = "https://registration-test.gocongress.org"
SOCKET_ADDRESS = "10.101.1.160"
SOCKET_PORT = 8081

BOOT_TIME = time.monotonic()

def logmsg(msg, exception=None):
    relative_time = time.monotonic() - BOOT_TIME
    try:
        raise Exception
    except Exception as exc:
        print(''.join(traceback.format_exception(None, exc, exc.__traceback__)))
    funcname = "LOL"
    lineno = 69
    print(f"[+{relative_time:.3f} {funcname}:{lineno}] {msg}")
    if exception:
        print(f"Exception {exception.__class__.__name__}: {str(exception)}")
        import traceback
        print(''.join(traceback.format_exception(None, exception, exception.__traceback__)))

class Sign:
    def __init__(self):
        self.text = b" init"
        self.progress = 0.0
        self.angle = 10
        
        self.init_display()
        self.init_groups()
        
        self.draw()
    
    def init_display(self):
        displayio.release_displays()
        self.matrix = rgbmatrix.RGBMatrix(
            width=32, bit_depth=4,
            rgb_pins=[
                board.MTX_R1,
                board.MTX_G1,
                board.MTX_B1,
                board.MTX_R2,
                board.MTX_G2,
                board.MTX_B2
            ],
            addr_pins=[
                board.MTX_ADDRA,
                board.MTX_ADDRB,
                board.MTX_ADDRC
            ],
            clock_pin=board.MTX_CLK,
            latch_pin=board.MTX_LAT,
            output_enable_pin=board.MTX_OE
        )
        self.display = framebufferio.FramebufferDisplay(self.matrix)
    
    def init_groups(self):
        g = displayio.Group()

        # We only use the built in font which we treat as being 7x14 pixels
        self.linelen = (64//7)+2

        # prepare the main groups
        self.l1 = displayio.Group()
        self.l2 = displayio.Group()
        g.append(self.l1)
        g.append(self.l2)
        self.display.root_group = g

        self.l1.y = 1
        self.l2.y = 16

        # Prepare the palettes and the individual characters' tiles
        self.sh = [displayio.Palette(2) for _ in range(self.linelen)]
        self.tg1 = [self.tilegrid(shi) for shi in self.sh]
        self.tg2 = [self.tilegrid(shi) for shi in self.sh]

        # Prepare a fast map from byte values to
        self.charmap = array.array('b', [terminalio.FONT.get_glyph(32).tile_index]) * 256
        for ch in range(256):
            glyph = terminalio.FONT.get_glyph(ch)
            if glyph is not None:
                self.charmap[ch] = glyph.tile_index

        # Set the X coordinates of each character in label 1, and add it to its group
        for idx, gi in enumerate(self.tg1):
            gi.x = 7 * idx
            self.l1.append(gi)

        # Set the X coordinates of each character in label 2, and add it to its group
        for idx, gi in enumerate(self.tg2):
            gi.x = 7 * idx
            self.l2.append(gi)

        self.progress_bitmap = displayio.Bitmap(32, 3, 2)
        progress_palette = displayio.Palette(2)
        progress_palette[0] = 0x000000  # Black/transparent
        progress_palette[1] = 0x00FF00  # Green

        progress_bar = displayio.TileGrid(
            bitmap=self.progress_bitmap,
            pixel_shader=progress_palette,
            width=1,
            height=1,
            x=0,
            y=13
        )
        self.display.root_group.append(progress_bar)

    def tilegrid(self, palette):
        return displayio.TileGrid(
            bitmap=terminalio.FONT.bitmap, pixel_shader=palette,
            width=1, height=1, tile_width=6, tile_height=12, default_tile=32)
    
    def set_label(self, text):
        new_text = b" " + str(text)
        if self.text != new_text:
            print(f"Sign: label set to '{text}'")
            self.text = new_text
            self.draw()

    def set_progress(self, progress):
        if self.progress != progress:
            print(f"Sign: progress bar set to {100*progress}%")
            self.progress = progress
            self.draw()
    
    def draw(self, angle=None):
        if angle:
            self.angle = angle
        for j in range(self.linelen):
            self.sh[j][1] = colorwheel(self.angle)  # Use a single color
            self.tg1[j][0] = self.charmap[self.text[j if j < len(self.text) else 0]]  # Top text
            self.tg2[j][0] = self.charmap[b" " [0]]  # Bottom text blank
        
        self.l1.x = 12 - 3*len(self.text)
        self.l1.y = -1
        
        width = int(32 * self.progress)
        for x in range(32):
            color = 1 if x < width else 0
            for y in range(3):  # Fill all rows for each column
                self.progress_bitmap[x, y] = color
        
        self.display.refresh(minimum_frames_per_second=0)

class SocketClient:
    def __init__(self, pool, event_name, address, port):
        self.pool = pool
        self.event_name = event_name
        self.address = address
        self.port = port
        self.buffer = bytearray()
        self.sock = None
    
    def connect(self):
        addr = (self.address, self.port)
        
        print(f"SocketClient: Opening socket connection TCP ({self.address}:{self.port})...")
        self.disconnect()
        self.sock = self.pool.socket(self.pool.AF_INET, self.pool.SOCK_STREAM)
        self.sock.connect(addr)
        self.sock.setblocking(False)

        print("SocketClient: Connected")
    
    def is_connected(self):
        if not self.sock:
            return False
        return True
    
    def disconnect(self):
        if self.sock is not None:
            print(f"SocketClient: Disconnecting")
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self.buffer = bytearray()
            
    def check_for_data(self):
        try:
            if not self.is_connected():
                self.connect()
            readbuf = bytearray(256)
            bytes_read = self.sock.recv_into(readbuf, 256)
            if bytes_read == 0:
                return None  # No data, return instantly
            self.buffer += readbuf[:bytes_read]
            print(f"SocketClient: Received data, {bytes_read} bytes, accumulated buffer: {self.buffer}\n")
            
            # Look for complete messages in buffer
            while True:
                # Find delimiter between length and data
                delim_pos = self.buffer.find(b'|')
                if delim_pos == -1:
                    break
                    
                # Extract and parse length
                try:
                    length = int(self.buffer[:delim_pos])
                except ValueError:
                    print("SocketClient: invalid socket data; didn't find length, forcing reconnect")
                    self.disconnect()
                    return None
                
                # Check if we have the full message
                total_len = delim_pos + 1 + length + 1 # Include delimiter and newline
                if len(self.buffer) < total_len:
                    break
                    
                # Extract message and remove from buffer
                message = self.buffer[delim_pos+1:delim_pos+2+length]
                if not message.endswith(b'\n'):
                    print("SocketClient: invalid socket data; message doesn't end with newline, forcing reconnect")
                    self.disconnect()
                    return None
                self.buffer = self.buffer[total_len:]
                
                # parse as json
                parsed = json.loads(message)
                if parsed["type"] == "event":
                    return parsed["data"]["event"]
                else:
                    return None
                
        except Exception as e:
            # If the exception is due to no data available, return instantly
            if isinstance(e, OSError) or "would block" in str(e).lower():
                return None
            print(f"SocketClient: error reading socket, {e}")
            self.disconnect()
        return None

class WebClient:
    def __init__(self, pool, event_name, url):
        self.url = url
        self.event_name = event_name
        self.hash = None
        self.pool = pool
        self.requests = adafruit_requests.Session(self.pool, ssl.create_default_context())
    
    def get_data_immediate(self):
        return self.get_data("force")

    def get_data(self, hash=None):
        try:
            url = self.url + f"/events/{self.event_name}/count"
            hash = hash or self.hash
            if hash is not None:
                url += f"?hash={hash}"
            
            print(f"WebClient: Getting data from {url}")
            response = self.requests.get(url)
            data = response.json()
            response.close()
            print(f"WebClient: received data, {data}")
            self.hash = data["response"]["hash"]
            return data["response"]["event"]
        except Exception as exc:
            print(f"WebClient: Error getting {url}: {exc}")
            return None

class DataSource:
    def __init__(self, pool, event_name, url, socket_address, socket_port, init_time=BOOT_TIME):
        self.pool = pool
        self.event_name = event_name
        self.web_client = WebClient(pool, event_name, url)
        self.socket_client = SocketClient(pool, event_name, socket_address, socket_port)
        self.last_update = None
        self.last_update_time = None
        self.init_time = init_time
    
    def close(self):
        self.socket_client.disconnect()
    
    def current_data(self):
        # read the socket to see if we have any new data.
        # it's possible to have multiple updates queued, so loop through to flush out the buffer
        valid_update = None
        while True:
            new_update = self.socket_client.check_for_data()
            if new_update is None:
                break
            else:
                valid_update = new_update
        
        if not valid_update:
            # socket had no data for us
            if not self.last_update:
                # we've never gotten data yet
                # if it's been a couple seconds since boot, do an HTTP GET
                # this is inconvenient because http requests are blocking...
                #
                # we wait the couple seconds because the server tries to send something right after we connect
                # but this is not guaranteed...
                if not self.last_update and time.monotonic() > self.init_time + 2.0:
                    print("DataSource: No data seen within 2 seconds of boot; trying synchronous request via HTTP")
                    valid_update = self.web_client.get_data_immediate()
            elif self.last_update_time - time.monotonic() > 5*60:
                # we haven't seen data in a few minutes, so go ahead and do an HTTP GET
                # the socket might be having problems...
                print("DataSource: No data seen in a while; trying synchronous request via HTTP")
                valid_update = self.web_client.get_data_immediate()
        
        if valid_update:
            self.last_update = valid_update
            self.last_update_time = time.monotonic()
            print(f"DataSource: received updated data")
        return self.last_update
        

class WifiConnection:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        
    def connect(self):
        print(f"WifiConnection: Connecting to SSID {self.ssid}...")
        wifi.radio.enabled = True
        wifi.radio.connect(self.ssid, self.password)
        print("WifiConnection: Connected!")

    def disconnect(self):
        print("WifiConnection: Disconnecting...")
        wifi.radio.stop_station()
        print("WifiConnection: Disconnected!")
    
    def wait_for_ip(self):
        while not self.ip():
            print("WifiConnection: Waiting for IP address...")
            time.sleep(1)        
        print(f"WifiConnection: Obtained IP, {self.ip()}")
    
    def ip(self):
        return wifi.radio.ipv4_address

class SignApp:
    def __init__(self, wifi_ssid, wifi_password, event_name, url, socket_address, socket_port):
        self.pool = socketpool.SocketPool(wifi.radio)
        self.wifi = WifiConnection(wifi_ssid, wifi_password)
        self.data_source = DataSource(self.pool, event_name, url, socket_address, socket_port)
        self.sign = Sign()
    
    def run(self):
        keep_going = True
        while keep_going:
            tick = 0
            try:
                self.sign.set_label("wifi")
                self.wifi.connect()
                self.wifi_handshake_time = time.monotonic()
                self.sign.set_label(" ip ")
                self.wifi.wait_for_ip()
                self.wifi_ip_time = time.monotonic()
                self.sign.set_label("data")
                self.data_source.init_time = self.wifi_ip_time
                
                while keep_going:
                    tick += 1
                    last_update = self.data_source.current_data()
                    if last_update is not None:
                        self.sign.set_label(last_update['total_attendees_scanned'])
                        self.sign.set_progress(last_update['total_attendees_scanned']/last_update['total_scannable'])
                    else:
                        self.sign.set_label(b" data")
                        self.sign.set_progress(0)
                    
                    last_update_time = self.data_source.last_update_time or self.wifi_ip_time
                    if last_update_time - time.monotonic() > 60*10:
                        print("Been too long since we saw data; maybe the wifi is bad? forcing a reboot")
                        keep_going = False
                    
                    self.sign.draw(tick/5)
                print("inner runloop has exited")
            except Exception as exc:
                print(f"SignApp: Runloop caught exception on tick {tick}: {exc}")
                print(''.join(traceback.format_exception(None, exc, exc.__traceback__)))
        
        print(f"outer runloop has exited")
        self.teardown()
            
    
    def teardown(self):
        self.data_source.close()
        self.wifi.disconnect()

while True:
    # logmsg(f"Boot-up. WIFI_SSID='{WIFI_SSID}', WIFI_PASSWORD='{WIFI_PASSWORD}', EVENT_NAME='{EVENT_NAME}', BADGEFILE_URL='{BADGEFILE_URL}', SOCKET_ADDRESS='{SOCKET_ADDRESS}', SOCKET_PORT={SOCKET_PORT}")
    SignApp(WIFI_SSID, WIFI_PASSWORD, EVENT_NAME, BADGEFILE_URL, SOCKET_ADDRESS, SOCKET_PORT).run()
