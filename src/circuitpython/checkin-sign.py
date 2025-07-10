import array
import wifi
import time
import ssl
import socketpool
import adafruit_requests
import json
import traceback
import random

from rainbowio import colorwheel
import board
import displayio
import framebufferio
import rgbmatrix
import terminalio

# Read secrets.json and parse config options
with open("secrets.json", "r") as f:
    secrets = json.load(f)

WIFI_SSID = secrets.get("wifi_ssid")
WIFI_PASSWORD = secrets.get("wifi_password") 
EVENT_NAME = secrets.get("event_name")
BADGEFILE_URL = secrets.get("badgefile_url")
SOCKET_ADDRESS = secrets.get("socket_address")
SOCKET_PORT = secrets.get("socket_port")

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
        self.was_connected = False
        self.connect_start_time = time.monotonic()
        self.sock = self.pool.socket(self.pool.AF_INET, self.pool.SOCK_STREAM)
        try:
            self.sock.connect(addr)
        except Exception as exc:
            pass
        self.sock.setblocking(False)

        print("SocketClient: Connected")
    
    def is_connected(self):
        # Note: This only checks if the socket object exists.
        # Actual connection state (like remote peer disconnect) is detected
        # in check_for_data() when recv_into() returns 0 bytes.
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
            self.was_connected = True
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
            if isinstance(e, OSError):
                if e.errno == errno.ENOTCONN or e.errno == errno.EINPROGRESS:
                    if not self.was_connected:
                        if time.monotonic() - self.connect_start_time < 10:
                            return None # give the socket a few seconds to connect
                        print("connection timed out; trying again")
                        self.connect()
                    else:
                        print("SocketClient: remote peer disconnected")
                        self.connect()
                    return None
                elif e.errno == errno.EAGAIN:
                    return None
                elif e.errno == errno.EINPROGRESS:
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
        print(f"WifiConnection: Connecting to SSID {self.ssid}, pw '{self.password}'...")
        wifi.radio.enabled = True
        wifi.radio.connect(self.ssid, self.password)
        print("WifiConnection: Connected!")

    def disconnect(self):
        print("WifiConnection: Disconnecting...")
        wifi.radio.stop_station()
        print("WifiConnection: Disconnected!")
    
    def wait_for_ip(self, callback=None):
        while not self.ip():
            print("WifiConnection: Waiting for IP address...")
            if callback is not None:
                if not callback():
                    return False
            time.sleep(1)        
        print(f"WifiConnection: Obtained IP, {self.ip()}")
        return True
    
    def ip(self):
        return wifi.radio.ipv4_address

class LEDSign:
    def __init__(self):
        self.width = 32
        self.height = 16
        
        # Initialize the display
        self.init_display()
        
        # Clear the display initially
        self.clear()
    
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
        
        # Create a bitmap with full color support (512 colors)
        self.bitmap = displayio.Bitmap(self.width, self.height, 512)
        self.palette = displayio.Palette(512)
        
        # Initialize palette with black at index 0
        self.palette[0] = 0x000000  # Black
        
        # Create tilegrid for display
        self.tilegrid = displayio.TileGrid(
            self.bitmap,
            pixel_shader=self.palette,
            width=1,
            height=1
        )
        
        # Create main group and set as root
        self.group = displayio.Group()
        self.group.append(self.tilegrid)
        self.display.root_group = self.group
        
        print("LED Sign initialized successfully")
    
    def clear(self):
        """Clear the entire grid (set all pixels off)"""
        for y in range(self.height):
            for x in range(self.width):
                self.bitmap[x, y] = 0  # Black
        self.display.refresh()
        print("Display cleared")
    
    def setPixel(self, x, y, color):
        """Set a given pixel to a specific color"""
        if 0 <= x < self.width and 0 <= y < self.height:
            # Find or add color to palette
            color_index = self.find_or_add_color(color)
            self.bitmap[x, y] = color_index
            self.display.refresh()
        else:
            print(f"Invalid pixel coordinates: ({x}, {y})")
    
    def find_or_add_color(self, color):
        """Find a color in the palette or add it if not present"""
        # Check if color already exists in palette
        for i in range(len(self.palette)):
            if self.palette[i] == color:
                return i
        
        # Add new color to palette
        for i in range(1, 512):  # Change from 256 to 512
            if self.palette[i] == 0:
                self.palette[i] = color
                return i
        
        # If palette is full, reuse a random slot (excluding 0)
        reuse_index = random.randint(1, 511)  # Change from 255 to 511
        self.palette[reuse_index] = color
        return reuse_index

class ProgressBar:
    def __init__(self, shimmering_sign, x, y, width, height, border_hue_offset=0.0, fill_hue_offset=0.0):
        """
        Initialize a progress bar
        
        Args:
            shimmering_sign: ShimmeringSign instance to draw on
            x, y: Top-left corner position
            width, height: Dimensions of the progress bar
            border_hue_offset: Hue offset in degrees for the border (default: 0.0)
            fill_hue_offset: Hue offset in degrees for the fill (default: 0.0)
        """
        self.shimmering_sign = shimmering_sign
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border_hue_offset = border_hue_offset
        self.fill_hue_offset = fill_hue_offset
        self.progress = 0.0  # 0.0 to 1.0
        self.last_fill_width = -1  # Track last fill width to detect changes
        
        print(f"ProgressBar initialized at ({x}, {y}) with size {width}x{height}")
    
    def set_progress(self, pct):
        """
        Set the progress percentage (0.0 to 1.0)
        
        Args:
            pct: Progress percentage from 0.0 to 1.0
        """
        new_progress = max(0.0, min(1.0, pct))
        
        # Calculate new fill width
        interior_width = max(0, self.width - 2)
        new_fill_width = int(interior_width * new_progress)
        
        # Only redraw if fill width has actually changed
        if new_fill_width != self.last_fill_width:
            self.progress = new_progress
            self.last_fill_width = new_fill_width
            print(f"Progress bar updating: {self.progress:.3f} -> fill_width: {new_fill_width}")
            self._draw()
    
    def _draw(self):
        """Draw the progress bar with border and fill"""
        # Calculate interior dimensions (inside the border)
        interior_x = self.x + 1
        interior_y = self.y + 1
        interior_width = max(0, self.width - 2)
        interior_height = max(0, self.height - 2)
        
        # Calculate fill width based on progress
        fill_width = int(interior_width * self.progress)
        
        # Draw border first
        self._draw_border()
        
        # Update interior pixels efficiently
        for dy in range(interior_height):
            for dx in range(interior_width):
                px, py = interior_x + dx, interior_y + dy
                if 0 <= px < self.shimmering_sign.width and 0 <= py < self.shimmering_sign.height:
                    if dx < fill_width:
                        # Fill area
                        self.shimmering_sign.set_pixel(px, py, self.fill_hue_offset)
                    else:
                        # Empty area
                        self.shimmering_sign.set_pixel(px, py, None)
    
    def _draw_border(self):
        """Draw the 1px border around the progress bar, leaving out corners for rounded look"""
        # Top border (skip corners)
        for dx in range(1, self.width - 1):
            px, py = self.x + dx, self.y
            if 0 <= px < self.shimmering_sign.width and 0 <= py < self.shimmering_sign.height:
                self.shimmering_sign.set_pixel(px, py, self.border_hue_offset)
        
        # Bottom border (skip corners)
        for dx in range(1, self.width - 1):
            px, py = self.x + dx, self.y + self.height - 1
            if 0 <= px < self.shimmering_sign.width and 0 <= py < self.shimmering_sign.height:
                self.shimmering_sign.set_pixel(px, py, self.border_hue_offset)
        
        # Left border (skip corners)
        for dy in range(1, self.height - 1):
            px, py = self.x, self.y + dy
            if 0 <= px < self.shimmering_sign.width and 0 <= py < self.shimmering_sign.height:
                self.shimmering_sign.set_pixel(px, py, self.border_hue_offset)
        
        # Right border (skip corners)
        for dy in range(1, self.height - 1):
            px, py = self.x + self.width - 1, self.y + dy
            if 0 <= px < self.shimmering_sign.width and 0 <= py < self.shimmering_sign.height:
                self.shimmering_sign.set_pixel(px, py, self.border_hue_offset)

class ShimmeringSign:
    def __init__(self, led_sign):
        self.led_sign = led_sign
        self.width = led_sign.width
        self.height = led_sign.height
        
        # Initialize pixel states: None = off, numeric = hue offset in degrees
        self.pixels = [[None for _ in range(self.height)] for _ in range(self.width)]
        
        # Color animation state
        self.hue = 0.0  # Current hue (0.0 to 1.0)
        self.hue_step = 0.005  # How much to increment hue each frame (reduced from 0.01)
        
        print("ShimmeringSign initialized")
    
    def set_pixel(self, x, y, hue_offset=0.0):
        """
        Set a pixel to on with optional hue offset, or off
        
        Args:
            x, y: Pixel coordinates
            hue_offset: Hue offset in degrees (0.0 = use gradient hue, 180.0 = opposite hue)
                       Use None to turn pixel off
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[x][y] = hue_offset
        else:
            print(f"Invalid pixel coordinates: ({x}, {y})")
    
    def clear(self, x=None, y=None, width=None, height=None):
        """Turn off pixels in the specified area (or all pixels if no bounds given)"""
        if x is None or y is None or width is None or height is None:
            # Clear all pixels
            for y in range(self.height):
                for x in range(self.width):
                    self.pixels[x][y] = None
        else:
            # Clear only the specified area
            for dy in range(height):
                for dx in range(width):
                    px, py = x + dx, y + dy
                    if 0 <= px < self.width and 0 <= py < self.height:
                        self.pixels[px][py] = None
    
    def draw_rectangle(self, x, y, width, height, hue_offset=0.0):
        """
        Draw a rectangle with top-left corner at (x, y)
        
        Args:
            x, y: Top-left corner position
            width, height: Rectangle dimensions
            hue_offset: Hue offset in degrees for all pixels in the rectangle
        """
        for dy in range(height):
            for dx in range(width):
                px, py = x + dx, y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    self.pixels[px][py] = hue_offset
    
    def render(self, x=None, y=None, width=None, height=None):
        """Render the current pixel states to the LED sign with gradient color"""
        # Define corner hues for the gradient with much smaller offsets to reduce discontinuities
        base_hue = self.hue
        
        # Use much smaller offsets to create smoother gradients
        top_left_hue = base_hue
        top_right_hue = (base_hue + 0.1) % 1.0  # Reduced from 0.2
        bottom_left_hue = (base_hue + 0.15) % 1.0  # Reduced from 0.4
        bottom_right_hue = (base_hue + 0.25) % 1.0  # Reduced from 0.6
        
        s = 0.7  # Saturation
        v = 0.3  # Value/brightness
        
        # Determine render bounds
        if x is None or y is None or width is None or height is None:
            # Render all pixels
            render_x, render_y = 0, 0
            render_width, render_height = self.width, self.height
        else:
            # Render only the specified area
            render_x, render_y = x, y
            render_width, render_height = width, height
        
        # Render pixels based on their state within the bounds
        for dy in range(render_height):
            for dx in range(render_width):
                px, py = render_x + dx, render_y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    pixel_state = self.pixels[px][py]
                    if pixel_state is not None:
                        # Calculate interpolated hue based on position
                        # Normalize coordinates to 0-1 range
                        nx = px / (self.width - 1) if self.width > 1 else 0
                        ny = py / (self.height - 1) if self.height > 1 else 0
                        
                        # Smooth bilinear interpolation with proper hue wrapping
                        # Top edge interpolation
                        top_hue = self._lerp_hue(top_left_hue, top_right_hue, nx)
                        # Bottom edge interpolation  
                        bottom_hue = self._lerp_hue(bottom_left_hue, bottom_right_hue, nx)
                        # Vertical interpolation
                        gradient_hue = self._lerp_hue(top_hue, bottom_hue, ny)
                        
                        # Apply pixel-specific hue offset
                        # Convert degrees to hue units (360 degrees = 1.0 hue)
                        hue_offset_units = pixel_state / 360.0
                        pixel_hue = (gradient_hue + hue_offset_units) % 1.0
                        
                        # Convert interpolated hue to RGB using improved conversion
                        color = self._hsv_to_rgb(pixel_hue, s, v)
                        
                        # Find or add color to palette
                        color_index = self.led_sign.find_or_add_color(color)
                        self.led_sign.bitmap[px, py] = color_index
                    else:
                        # Clear pixels that are None within the render bounds
                        self.led_sign.bitmap[px, py] = 0  # Black
        
        # Don't refresh display here - let the calling code handle it
        # self.led_sign.display.refresh()
        
        # Update hue for next frame
        self.hue = (self.hue + self.hue_step) % 1.0
    
    def _hsv_to_rgb(self, h, s, v):
        """Convert HSV to RGB with improved handling of edge cases"""
        if s == 0.0:
            # When saturation is 0, we get grayscale
            rgb_val = int(v * 255)
            return (rgb_val << 16) | (rgb_val << 8) | rgb_val
        
        # Normalize hue to 0-1 range
        h = h % 1.0
        
        # Convert hue to 0-6 range for easier calculation
        h6 = h * 6.0
        
        # Calculate chroma and intermediate values
        c = v * s
        x = c * (1 - abs((h6 % 2) - 1))
        m = v - c
        
        # Determine RGB values based on hue sector
        if h6 < 1:
            r, g, b = c, x, 0
        elif h6 < 2:
            r, g, b = x, c, 0
        elif h6 < 3:
            r, g, b = 0, c, x
        elif h6 < 4:
            r, g, b = 0, x, c
        elif h6 < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        # Add value offset and convert to 0-255 range
        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        
        # Clamp values to valid range
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        # Return as 24-bit color
        return (r << 16) | (g << 8) | b
    
    def _lerp_hue(self, h1, h2, t):
        """Linear interpolation between two hues, handling wrapping properly"""
        # Normalize both hues to 0-1 range
        h1 = h1 % 1.0
        h2 = h2 % 1.0
        
        # Handle the case where we need to interpolate across the 0/1 boundary
        if abs(h2 - h1) > 0.5:
            if h1 < h2:
                h1 += 1.0
            else:
                h2 += 1.0
        
        # Interpolate
        result = h1 + (h2 - h1) * t
        
        # Wrap back to 0-1 range
        return result % 1.0

class Glyph:
    def __init__(self, char):
        self.char = char
        self.width = 6
        self.height = 10
        
        # Define the pixel patterns for digits 0-9
        # Each digit is 6x10 pixels, stored as a list of rows
        self.digit_patterns = {
            '0': [
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            '1': [
                "   ██ ",
                " ████ ",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                " █████"
            ],
            '2': [
                " ████ ",
                "██  ██",
                "    ██",
                "   ██ ",
                "  ██  ",
                " ██   ",
                "██    ",
                "██    ",
                "██  ██",
                "██████"
            ],
            '3': [
                " ████ ",
                "██  ██",
                "    ██",
                "    ██",
                " ████ ",
                "    ██",
                "    ██",
                "    ██",
                "██  ██",
                " ████ "
            ],
            '4': [
                "   ██ ",
                "  ███ ",
                " ████ ",
                "██ ██ ",
                "██ ██ ",
                "██████",
                "   ██ ",
                "   ██ ",
                "   ██ ",
                "   ██ "
            ],
            '5': [
                "██████",
                "██    ",
                "██    ",
                "██    ",
                "█████ ",
                "    ██",
                "    ██",
                "    ██",
                "██  ██",
                " ████ "
            ],
            '6': [
                " ████ ",
                "██  ██",
                "██    ",
                "██    ",
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            '7': [
                "██████",
                "██  ██",
                "    ██",
                "   ██ ",
                "  ██  ",
                " ██   ",
                "██    ",
                "██    ",
                "██    ",
                "██    "
            ],
            '8': [
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            '9': [
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                " █████",
                "    ██",
                "    ██",
                "    ██",
                "██  ██",
                " ████ "
            ],
            'A': [
                "  ██  ",
                " ████ ",
                "██  ██",
                "██  ██",
                "██████",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'B': [
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "█████ "
            ],
            'C': [
                " ████ ",
                "██  ██",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██  ██",
                " ████ "
            ],
            'D': [
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "█████ "
            ],
            'E': [
                "██████",
                "██    ",
                "██    ",
                "██    ",
                "█████ ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██████"
            ],
            'F': [
                "██████",
                "██    ",
                "██    ",
                "██    ",
                "█████ ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    "
            ],
            'G': [
                " ████ ",
                "██  ██",
                "██    ",
                "██    ",
                "██    ",
                "██ ███",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            'H': [
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██████",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'I': [
                "██████",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "██████"
            ],
            'J': [
                "██████",
                "    ██",
                "    ██",
                "    ██",
                "    ██",
                "    ██",
                "    ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            'K': [
                "██  ██",
                "██  ██",
                "██ ██ ",
                "████  ",
                "███   ",
                "████  ",
                "██ ██ ",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'L': [
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██████"
            ],
            'M': [
                "██  ██",
                "██████",
                "██████",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'N': [
                "██  ██",
                "███ ██",
                "██████",
                "██████",
                "██ ███",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'O': [
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            'P': [
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "█████ ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██    "
            ],
            'Q': [
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██ ██ ",
                "██ ███ ",
                " ███ █"
            ],
            'R': [
                "█████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "█████ ",
                "██ ██ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'S': [
                " ████ ",
                "██  ██",
                "██    ",
                "██    ",
                " ████ ",
                "    ██",
                "    ██",
                "    ██",
                "██  ██",
                " ████ "
            ],
            'T': [
                "██████",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  "
            ],
            'U': [
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ "
            ],
            'V': [
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ ",
                " ████ ",
                "  ██  "
            ],
            'W': [
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                "█    █",
                "█    █",
                "█ ██ █",
                "██████",
                "██  ██",
                "██  ██"
            ],
            'X': [
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ ",
                " ████ ",
                " ████ ",
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██"
            ],
            'Y': [
                "██  ██",
                "██  ██",
                "██  ██",
                "██  ██",
                " ████ ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  ",
                "  ██  "
            ],
            'Z': [
                "██████",
                "    ██",
                "   ██ ",
                "  ██  ",
                " ██   ",
                "██    ",
                "██    ",
                "██    ",
                "██    ",
                "██████"
            ],
            '%': [
                "██  ██",
                "██  ██",
                "   ██ ",
                "   ██ ",
                "  ██  ",
                "  ██  ",
                " ██   ",
                " ██   ",
                "██  ██",
                "██  ██"
            ],
            '.': [
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "  ██  ",
                "  ██  "
            ],
            ' ': [
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      ",
                "      "
            ]
        }
    
    def drawInto(self, ary, x, y):
        """Draw the glyph into the array at the specified x, y offset"""
        if self.char not in self.digit_patterns:
            print(f"Unsupported character: {self.char}")
            return
        
        pattern = self.digit_patterns[self.char]
        
        # Check bounds
        if x < 0 or y < 0 or x + self.width > len(ary) or y + self.height > len(ary[0]):
            print(f"Glyph would be out of bounds at ({x}, {y})")
            return
        
        # Draw the pattern into the array
        for row in range(self.height):
            for col in range(self.width):
                if pattern[row][col] == '█':
                    ary[x + col][y + row] = 0.0  # On pixel with 0.0 hue offset
                else:
                    ary[x + col][y + row] = None  # Off pixel

class GlyphWriter:
    def __init__(self, target_array, x, y):
        self.target_array = target_array
        self.x = x
        self.y = y
        self.glyph_width = 6
        self.glyph_height = 10
        self.glyph_spacing = 1  # 1 pixel of blank space between glyphs
    
    def write_string(self, string):
        """Write a string of characters into the target array starting at the constructor position"""
        current_x = self.x
        
        for char in string.upper():
            if char.isdigit() or char.isupper() or char == '%' or char == ' ':
                glyph = Glyph(char)
                glyph.drawInto(self.target_array, current_x, self.y)
                current_x += self.glyph_width + self.glyph_spacing
            else:
                # Skip non-digit/non-uppercase characters or add a space
                current_x += self.glyph_width + self.glyph_spacing
        
        return current_x - self.glyph_spacing  # Return the end position (without trailing spacing)

def marching_pixel_demo(sign):
    """Run a marching pixel demo on the LED sign"""
    pixel_x = 0
    pixel_y = 0
    
    # Set initial pixel
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    color = (r << 16) | (g << 8) | b
    sign.setPixel(pixel_x, pixel_y, color)
    print(f"Initial pixel at ({pixel_x}, {pixel_y}) with color 0x{color:06X}")
    
    while True:
        try:
            # Clear current position
            sign.setPixel(pixel_x, pixel_y, 0x000000)  # Black
            
            # Move to next position
            pixel_x += 1
            
            # Wrap to next row if at end of current row
            if pixel_x >= sign.width:
                pixel_x = 0
                pixel_y += 1
                
                # Wrap back to top if at bottom
                if pixel_y >= sign.height:
                    pixel_y = 0
            
            # Generate a random color for new position
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            color = (r << 16) | (g << 8) | b
            
            # Set new position with random color
            sign.setPixel(pixel_x, pixel_y, color)
            print(f"x={pixel_x}, y={pixel_y}, color=0x{color:06X}")
            
            # Wait 100ms before next move
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error in marching pixel demo: {e}")
            traceback.print_exception(e)
            time.sleep(1)


class SignApp:
    def __init__(self, wifi_ssid, wifi_password, event_name, url, socket_address, socket_port):
        self.pool = socketpool.SocketPool(wifi.radio)
        self.wifi = WifiConnection(wifi_ssid, wifi_password)
        self.data_source = DataSource(self.pool, event_name, url, socket_address, socket_port)
        self.led_sign = LEDSign()
        self.shimmering_sign = ShimmeringSign(self.led_sign)
        self.progress_bar = ProgressBar(
            shimmering_sign=self.shimmering_sign,
            x=0,  # Start at left edge
            y=12,  # Position at bottom (16 - 4 = 12)
            width=32,  # Full width
            height=4,  # 4px tall
            border_hue_offset=240.0,  # Border hue offset
            fill_hue_offset=120.0  # Fill hue offset
        )
        self.sign_text = ""
    
    def run(self):
        keep_going = True
        while keep_going:
            tick = 0
            try:
                self.show_msg("WIFI", draw=True)
                self.wifi.connect()
                self.wifi_handshake_time = time.monotonic()

                self.show_msg("IP", draw=True)
                def ip_wait_callback():
                    self.shimmering_sign.render()
                    self.led_sign.display.refresh()
                    return time.monotonic() - self.wifi_handshake_time < 60*5
                keep_going = self.wifi.wait_for_ip(ip_wait_callback)
                
                if keep_going:
                    self.wifi_ip_time = time.monotonic()
                    self.led_sign.clear()
                    self.show_msg("DATA", draw=True)
                    self.data_source.init_time = self.wifi_ip_time
                
                while keep_going:
                    tick += 1
                    print(tick)
                    last_update = self.data_source.current_data()
                    if last_update is not None:
                        self.show_msg(last_update['total_attendees_scanned'], draw=False)
                        self.progress_bar.set_progress(last_update['total_attendees_scanned']/last_update['total_scannable'])
                        self.shimmering_sign.render()
                        self.led_sign.display.refresh()
                    else:
                        self.show_msg("DATA", draw=False)
                    
                    last_update_time = self.data_source.last_update_time or self.wifi_ip_time
                    if last_update_time - time.monotonic() > 60*10:
                        print("Been too long since we saw data; maybe the wifi is bad? forcing a reboot")
                        keep_going = False
                    
                print("inner runloop has exited")
            except Exception as exc:
                print(f"SignApp: Runloop caught exception on tick {tick}: {exc}")
                print(''.join(traceback.format_exception(None, exc, exc.__traceback__)))
        
        print(f"outer runloop has exited")
        self.teardown()
    
    def show_msg(self, msg, draw=False):
        msg = str(msg)
        if msg == self.sign_text and not draw:
            return True
        print(f"Sign text: {msg}, draw={draw}")
        # Only clear the text area (top 12 rows), not the entire display
        self.shimmering_sign.clear(0, 0, self.led_sign.width, 12)
        txt_width = 7*len(msg) - 1
        txt_height = 10
        x = (self.led_sign.width  - txt_width)  // 2
        y = 1 # (self.led_sign.height - txt_height) // 2
        if draw:
            self.shimmering_sign.clear(0, 0, self.led_sign.width, 12)
        
        writer = GlyphWriter(self.shimmering_sign.pixels, x, y)
        writer.write_string(msg)
        if draw:
            self.shimmering_sign.render(0, 0, self.led_sign.width, 12)
            self.led_sign.display.refresh()
        self.sign_text = msg
    
    def teardown(self):
        self.data_source.close()
        self.wifi.disconnect()

def main():
    print("Starting LED Sign Demo")
    
    # Run the shimmering demo
    # shimmering_demo()
    # text_demo()
    SignApp(WIFI_SSID, WIFI_PASSWORD, EVENT_NAME, BADGEFILE_URL, SOCKET_ADDRESS, SOCKET_PORT).run()



if __name__ == "__main__":
    main()
