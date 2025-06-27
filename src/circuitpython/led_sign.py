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

WIFI_SSID = "thewall"
WIFI_PASSWORD = "Portal-Seduce3=EDge"
EVENT_NAME = "signtest"
BADGEFILE_URL = "https://registration-test.gocongress.org"
SOCKET_ADDRESS = "10.101.1.160"
SOCKET_PORT = 8081

BOOT_TIME = time.monotonic()

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
        
        # Create a bitmap with full color support (256 colors)
        self.bitmap = displayio.Bitmap(self.width, self.height, 256)
        self.palette = displayio.Palette(256)
        
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
        for i in range(1, 256):  # Start from 1 since 0 is black
            if self.palette[i] == 0:  # Empty slot
                self.palette[i] = color
                return i
        
        # If palette is full, reuse a random slot (excluding 0)
        reuse_index = random.randint(1, 255)
        self.palette[reuse_index] = color
        return reuse_index

class ProgressBar:
    def __init__(self, led_sign, x, y, width, height, border_color=0xFF8000, fill_color=0xFF0000):
        """
        Initialize a progress bar
        
        Args:
            led_sign: LEDSign instance to draw on
            x, y: Top-left corner position
            width, height: Dimensions of the progress bar
            border_color: Color for the border (default: orange 0xFF8000)
            fill_color: Color for the fill (default: red 0xFF0000)
        """
        self.led_sign = led_sign
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border_color = border_color
        self.fill_color = fill_color
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
        
        # Draw border first (only if it fits within bounds)
        self._draw_border()
        
        # Get the fill color index once
        fill_color_index = self.led_sign.find_or_add_color(self.fill_color)
        
        # Update interior pixels efficiently
        for dy in range(interior_height):
            for dx in range(interior_width):
                px, py = interior_x + dx, interior_y + dy
                if 0 <= px < self.led_sign.width and 0 <= py < self.led_sign.height:
                    if dx < fill_width:
                        # Fill area
                        self.led_sign.bitmap[px, py] = fill_color_index
                    else:
                        # Empty area
                        self.led_sign.bitmap[px, py] = 0  # Black
        
        # Don't refresh display here - let the calling code handle it
        # self.led_sign.display.refresh()
    
    def _draw_border(self):
        """Draw the 1px border around the progress bar"""
        # Top border
        for dx in range(self.width):
            px, py = self.x + dx, self.y
            if 0 <= px < self.led_sign.width and 0 <= py < self.led_sign.height:
                color_index = self.led_sign.find_or_add_color(self.border_color)
                self.led_sign.bitmap[px, py] = color_index
        
        # Bottom border
        for dx in range(self.width):
            px, py = self.x + dx, self.y + self.height - 1
            if 0 <= px < self.led_sign.width and 0 <= py < self.led_sign.height:
                color_index = self.led_sign.find_or_add_color(self.border_color)
                self.led_sign.bitmap[px, py] = color_index
        
        # Left border
        for dy in range(self.height):
            px, py = self.x, self.y + dy
            if 0 <= px < self.led_sign.width and 0 <= py < self.led_sign.height:
                color_index = self.led_sign.find_or_add_color(self.border_color)
                self.led_sign.bitmap[px, py] = color_index
        
        # Right border
        for dy in range(self.height):
            px, py = self.x + self.width - 1, self.y + dy
            if 0 <= px < self.led_sign.width and 0 <= py < self.led_sign.height:
                color_index = self.led_sign.find_or_add_color(self.border_color)
                self.led_sign.bitmap[px, py] = color_index

class ShimmeringSign:
    def __init__(self, led_sign):
        self.led_sign = led_sign
        self.width = led_sign.width
        self.height = led_sign.height
        
        # Initialize pixel states (True = on, False = off)
        self.pixels = [[False for _ in range(self.height)] for _ in range(self.width)]
        
        # Color animation state
        self.hue = 0.0  # Current hue (0.0 to 1.0)
        self.hue_step = 0.005  # How much to increment hue each frame (reduced from 0.01)
        
        print("ShimmeringSign initialized")
    
    def set_pixel(self, x, y, state):
        """Set a pixel to on (True) or off (False)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[x][y] = state
        else:
            print(f"Invalid pixel coordinates: ({x}, {y})")
    
    def clear(self, x=None, y=None, width=None, height=None):
        """Turn off pixels in the specified area (or all pixels if no bounds given)"""
        if x is None or y is None or width is None or height is None:
            # Clear all pixels
            for y in range(self.height):
                for x in range(self.width):
                    self.pixels[x][y] = False
        else:
            # Clear only the specified area
            for dy in range(height):
                for dx in range(width):
                    px, py = x + dx, y + dy
                    if 0 <= px < self.width and 0 <= py < self.height:
                        self.pixels[px][py] = False
    
    def draw_rectangle(self, x, y, width, height, fill=True):
        """Draw a rectangle with top-left corner at (x, y)"""
        for dy in range(height):
            for dx in range(width):
                px, py = x + dx, y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    self.pixels[px][py] = fill
    
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
        
        # Only render pixels that are set to True in the pixels array within the bounds
        for dy in range(render_height):
            for dx in range(render_width):
                px, py = render_x + dx, render_y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    if self.pixels[px][py]:
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
                        pixel_hue = self._lerp_hue(top_hue, bottom_hue, ny)
                        
                        # Convert interpolated hue to RGB using improved conversion
                        color = self._hsv_to_rgb(pixel_hue, s, v)
                        
                        # Find or add color to palette
                        color_index = self.led_sign.find_or_add_color(color)
                        self.led_sign.bitmap[px, py] = color_index
                    else:
                        # Clear pixels that are False within the render bounds
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
            # Capital letters A-Z
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
                "██ ██ ",
                " ████ "
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
                    ary[x + col][y + row] = True
                else:
                    ary[x + col][y + row] = False

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
            if char.isdigit() or char.isupper():
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

def shimmering_demo():
    """Run a shimmering demo with a counter from 0 to 2000 and a progress bar"""
    print("Starting ShimmeringSign Demo with Progress Bar")
    
    # Initialize the LED sign
    led_sign = LEDSign()
    
    # Initialize the shimmering sign
    shimmer_sign = ShimmeringSign(led_sign)
    
    # Initialize the progress bar (full width, 4px tall, orange border, red fill)
    progress_bar = ProgressBar(
        led_sign=led_sign,
        x=0,  # Start at left edge
        y=12,  # Position at bottom (16 - 4 = 12)
        width=32,  # Full width
        height=4,  # 4px tall
        border_color=0x002020,  # Dark blue border
        fill_color=0x8000FF  # Bright purple fill
        
    )
    
    # Counter variables
    counter = 0
    max_count = 2000
    
    # Main animation loop
    while True:
        try:
            # Clear only the text area (excluding progress bar area)
            shimmer_sign.clear(0, 0, led_sign.width, 12)  # Clear top 12 rows only
            
            # Draw progress bar first (so it stays stable)
            progress_pct = (counter % 100) / 100
            progress_bar.set_progress(progress_pct)
            
            # Convert counter to string (no zero-prefixing)
            counter_str = str(counter)
            
            # Calculate center position for the text
            # Each character is 6 pixels wide + 1 pixel spacing between characters
            num_digits = len(counter_str)
            text_width = num_digits * 6 + (num_digits - 1) * 1  # characters * 6 + spaces * 1
            center_x = (led_sign.width - text_width) // 2
            center_y = 1  # Each glyph is 10 pixels tall
            
            # Create a glyph writer for the current position
            writer = GlyphWriter(shimmer_sign.pixels, center_x, center_y)
            
            # Draw the current counter value
            writer.write_string(counter_str)
            
            # Render the shimmering text only in the text area (excluding progress bar)
            shimmer_sign.render(0, 0, led_sign.width, 12)  # Render top 12 rows only
            
            # Refresh display once after all drawing is complete
            led_sign.display.refresh()
            
            # Increment counter
            counter = (counter + 1) % (max_count + 1)
            
            # Wait before next frame
            time.sleep(0.1)  # Slower update rate for readable counting
            
        except Exception as e:
            print(f"Error in shimmering demo: {e}")
            traceback.print_exception(e)
            time.sleep(1)

def text_demo():
    led_sign = LEDSign()
    shimmer_sign = ShimmeringSign(led_sign)
    text = "data"
    num_chars = len(text)
    text_width = num_chars * 6 + (num_chars - 1) * 1  # characters * 6 + spaces * 1
    center_x = (led_sign.width - text_width) // 2
    center_y = (led_sign.height - 10) // 2
    writer = GlyphWriter(shimmer_sign.pixels, center_x, center_y)
    writer.write_string(text)

    while True:
        shimmer_sign.render(0, 0, led_sign.width, 16)
        led_sign.display.refresh()
        # time.sleep(0.1)  # Slower update rate for readable counting


def main():
    print("Starting LED Sign Demo")
    
    # Run the shimmering demo
    # shimmering_demo()
    text_demo()



if __name__ == "__main__":
    print("HOWDY!!!")
    main()
