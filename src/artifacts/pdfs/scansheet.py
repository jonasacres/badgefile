from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

import os
import io
from pylibdmtx.pylibdmtx import encode
from PIL import Image as PILImage

# make a test sheet with a bunch of data matrices on it so we can test scanning

class ScanSheet:
  def __init__(self, badgefile):
    self.badgefile = badgefile
    self.path = "artifacts/scansheet.pdf"

  def draw(self):
    # Create parent directories for the badge file if they don't exist
    os.makedirs(os.path.dirname(self.path), exist_ok=True)
    
    # Initialize the canvas and layout the badge
    self.canvas = canvas.Canvas(self.path, pagesize=(8.5*inch, 11*inch))

    margin_size = 0.25 * inch
    datamatrix_size = 0.7 * inch
    cell_size = datamatrix_size + margin_size
    grid_width = int(8.5*inch / cell_size)
    grid_height = int(11*inch / cell_size)

    # Get all attendees
    attendees = [att for att in self.badgefile.attendees() if not att.is_cancelled()]
    
    # Iterate over every x, y in grid
    for row in range(grid_height):
      for col in range(grid_width):
        # Calculate position for this data matrix
        x = margin_size + (col * cell_size)
        y = 11*inch - margin_size - (row * cell_size) - datamatrix_size
        
        # Get an attendee (cycling through the list)
        index = (row * grid_width + col) % len(attendees)
        attendee = attendees[index]
          
        # Generate Data Matrix with attendee ID
        data = attendee.datamatrix_content()
        encoded = encode(data, size='14x14')
        
        # Convert to PIL Image
        dm_img = PILImage.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
        
        # Create a BytesIO buffer to hold the image data
        buffer = io.BytesIO()
        dm_img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Create an ImageReader from the buffer
        img_reader = ImageReader(buffer)
        
        # Draw the Data Matrix
        self.canvas.drawImage(img_reader, x, y, width=datamatrix_size, height=datamatrix_size)
        
        # Draw attendee ID below the data matrix
        self.canvas.setFont("Helvetica", 8)
        self.canvas.drawCentredString(
          x + datamatrix_size/2, 
          y - 10, 
          f"#{attendee.id()}"
        )

    # all done; make the PDF
    self.canvas.showPage()
    self.canvas.save()
    return self
