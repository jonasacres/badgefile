import os
from log.logger import log

class DonorPage:
  """Provides a list of donors by badgefile ID and tier level in HTML format."""

  def __init__(self, badgefile):
    self.badgefile = badgefile
  
  def generate(self, path=None):
    if path is None:
      path = "artifacts/html/friends_of_congress/index.html"
    
    log.info(f"donor_report: generating donor HTML report at {path}")
    
    # Create directory structure if it doesn't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Get donor data
    donors = [donor for donor in self.badgefile.attendees() if donor.info().get('donation_tier') != 'nondonor' and float(donor.info().get('donation_amount', 0.0)) > 0]
    for donor in donors:
      donor.recalculate_donation_info()
    
    # Sort donors by donation amount, highest first
    donors.sort(key=lambda x: float(x.info().get('donation_amount', 0.0)), reverse=True)
    
    # Generate HTML content
    html_content = self._generate_html(donors)
    
    # Write HTML to file
    with open(path, 'w', encoding='utf-8') as file:
      file.write(html_content)
    
    log.debug(f"donor_report: Generation complete, {len(donors)} donors listed.")
  
  def _generate_html(self, donors):
    """Generate HTML content for the donor report."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Friends of the 2025 US Go Congress</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .banner {
            background-color: #3a5a78;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        h1 {
            margin-top: 0;
        }
        .donor-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .donor-card {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .tier {
            font-weight: bold;
            color: #3a5a78;
            margin-bottom: 5px;
        }
        .name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
            color: #222;
        }
        .anonymous {
            font-style: italic;
            color: #777;
            font-size: 1.0em;
        }
        .footer {
            margin-top: 40px;
            text-align: center;
            color: #777;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="banner">
        <h1>Friends of the 2025 US Go Congress</h1>
        <p>The American Go Association thanks this year's Friends of the Congress donors for their generous support. Thank you to each our of donors for helping make the 2025 US Go Congress a reality!</p>
    </div>
    
    <div class="donor-list">
"""
    
    # Add donor cards
    for donor in donors:
      name = donor.info()['donation_name']
      if donor.info()['donation_is_anonymous'] or not name:
        name = '<span class="anonymous">Anonymous Donor</span>'
      
      html += f"""        <div class="donor-card">
            <div class="name">{name}</div>
            <div class="tier">{donor.info()['donation_tier'].title()} Tier</div>
        </div>
"""
    
    # Close HTML
    html += """    </div>
    
    <div class="footer">
        <p>The American Go Association appreciates your continued support.</p>
    </div>
</body>
</html>"""
    
    return html

