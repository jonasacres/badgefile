import os
from log.logger import log
from datasources.clubexpress.payments_report import PaymentsReport

class DonorPage:
  """Provides a list of donors by badgefile ID and tier level in HTML format."""

  def __init__(self, badgefile):
    self.badgefile = badgefile

  def donors_from_registration(self):
    donors = [donor for donor in self.badgefile.attendees() if donor.info().get('donation_tier') != 'nondonor' and float(donor.info().get('donation_amount', 0.0)) > 0]
    for donor in donors:
      donor.recalculate_donation_info()
    return [donor.info() for donor in donors]
  
  def tier_for_amount(self, amount):
    if amount < 10:
      return "nondonor"
    elif amount < 50:
      return "silver"
    elif amount < 250:
      return "gold"
    else:
      return "platinum"
  
  def donors_from_renewals(self):
    report = PaymentsReport.latest()
    transactions = report.transactions()
    donor_rows = []

    for tx in transactions:
      for row in tx['rows']:
        if "Support the US Go Congress" in row['description'] or "Donation: US Go Congress" in row['description']:
          donor_rows.append({
            "donation_name": f"{tx['name'][0]} {tx['name'][1]}",
            "donation_tier": self.tier_for_amount(row['amount']),
            "donation_amount": row['amount'],
            "donation_is_anonymous": False,
          })
    
    return donor_rows
  
  def merge_donors(self, donors):
    by_name = {}
    
    for donor in donors:
      lc_name = donor['donation_name'].lower()
      if not lc_name in by_name:
        by_name[lc_name] = []
      by_name[lc_name].append(donor)
    
    merged_list = []
    for name, donors in by_name.items():
      if name in ["anon", "anonymous"]:
        merged_list += donors
      else:
        merged_amount = 0.0
        for donor in donors:
          if donor["donation_is_anonymous"]:
            merged_list.append(donor)
          else:
            merged_amount += donor['donation_amount']
        if merged_amount > 0:
          merged_donor = {
            'donation_name': donors[0]['donation_name'],
            'donation_amount': merged_amount,
            'donation_tier': self.tier_for_amount(merged_amount),
            'donation_is_anonymous': False,
          }
          print(f"{merged_donor['donation_name']} ${merged_donor['donation_amount']} -> {merged_donor['donation_tier']}")
          merged_list.append(merged_donor)
    
    return merged_list
  
  def generate(self, path=None):
    if path is None:
      path = "artifacts/html/friends_of_congress/index.html"
    
    log.info(f"donor_report: generating donor HTML report at {path}")
    
    # Create directory structure if it doesn't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Get donor data
    donors = self.donors_from_registration() + self.donors_from_renewals()
    donors = self.merge_donors(donors)
    
    # Sort donors by donation amount, highest first
    donors.sort(key=lambda x: float(x.get('donation_amount', 0.0)), reverse=True)
    
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
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
            overflow: hidden;
            background-size: 200% 100%;
        }
        .donor-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        .donor-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: repeating-linear-gradient(
                45deg,
                rgba(255, 255, 255, 0.1),
                rgba(255, 255, 255, 0.1) 1px,
                transparent 1px,
                transparent 5px
            );
            pointer-events: none;
        }
        .tier {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .tier-range {
            font-size: 0.9em;
            margin-top: 5px;
            color: #555;
        }
        .platinum {
            background: linear-gradient(135deg, #e5e4e2 0%, #b8b8b8 30%, #e8e8e8 50%, #b8b8b8 70%, #e5e4e2 100%);
            border-left: 5px solid #a9a9a9;
            position: relative;
            overflow: hidden;
            background-size: 200% 200%;
            animation: gradientShift 30s ease infinite;
        }
        
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes brushEffect {
            0% { background-position: -100% 0; }
            100% { background-position: 100% 0; }
        }
        
        .platinum::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, 
                rgba(255,255,255,0) 0%, 
                rgba(255,255,255,0.2) 25%, 
                rgba(255,255,255,0.2) 50%, 
                rgba(255,255,255,0) 100%);
            background-size: 200% 100%;
            animation: brushEffect 3s infinite linear;
            pointer-events: none;
        }
        .platinum:before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 30%, rgba(255,0,0,0.8) 0%, rgba(255,255,255,0) 6%),
                radial-gradient(circle at 50% 60%, rgba(0,255,0,0.8) 0%, rgba(255,255,255,0) 7%),
                radial-gradient(circle at 80% 40%, rgba(0,0,255,0.8) 0%, rgba(255,255,255,0) 10%),
                radial-gradient(circle at 30% 80%, rgba(255,255,0,0.8) 0%, rgba(255,255,255,0) 8%),
                radial-gradient(circle at 70% 10%, rgba(255,0,255,0.8) 0%, rgba(255,255,255,0) 9%),
                radial-gradient(circle at 12% 45%, rgba(0,255,255,0.8) 0%, rgba(255,255,255,0) 2%);
            mix-blend-mode: color-dodge;
            pointer-events: none;
            opacity: 0.9;
            animation: sparkle 5s infinite alternate;
        }
        @keyframes sparkle {
            0% {
                opacity: 0.7;
                background-position: 0% 0%;
            }
            50% {
                opacity: 1;
            }
            100% {
                opacity: 0.7;
                background-position: 100% 100%;
            }
        }
        .platinum .tier {
            color: #404040;
            text-shadow: 0px 1px 1px rgba(255,255,255,0.7);
        }
        .gold {
            background: linear-gradient(135deg, #fff4d1 0%, #ffd700 50%, #fff4d1 100%);
            border-left: 5px solid #FFD700;
        }
        .gold .tier {
            color: #8B6914;
        }
        .silver {
            background: linear-gradient(135deg, #f5f5f5 0%, #c0c0c0 50%, #f5f5f5 100%);
            border-left: 5px solid #C0C0C0;
        }
        .silver .tier {
            color: #505050;
        }
        .name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
            color: #222;
            text-shadow: 0px 1px 1px rgba(255,255,255,0.5);
            position: relative;
            z-index: 1;
        }
        .platinum .name {
            color: #000000;
            text-shadow: 0px 1px 2px rgba(128,128,128,0.7);
            font-size: 1.4em;
            background: linear-gradient(to right, #000000, #202020);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .anonymous {
            font-style: italic;
            color: #555;
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
    
    # Group donors by tier and separate anonymous from named donors
    tier_groups = {
        "platinum": {"named": [], "anonymous": 0},
        "gold": {"named": [], "anonymous": 0},
        "silver": {"named": [], "anonymous": 0}
    }
    
    for donor in donors:
      tier = donor['donation_tier'].lower()
      if tier not in tier_groups:
          continue
          
      if donor['donation_is_anonymous'] or not donor['donation_name']:
          tier_groups[tier]["anonymous"] += 1
      else:
          tier_groups[tier]["named"].append(donor)
    
    # Add donor cards by tier, with named donors first followed by anonymous group
    for tier in ["platinum", "gold", "silver"]:
        # Add named donors in this tier
        for donor in tier_groups[tier]["named"]:
            name = donor['donation_name']
            tier_class = tier
            tier_range = ""
            
            if tier == "platinum":
                tier_range = "$250+"
            elif tier == "gold":
                tier_range = "$50-$249"
            elif tier == "silver":
                tier_range = "$10-$49"
            
            html += f"""        <div class="donor-card {tier_class}">
            <div class="name">{name}</div>
            <div class="tier">{tier.title()} Tier</div>
            <div class="tier-range">{tier_range}</div>
        </div>
"""
        
        # Add anonymous donors card if there are any
        if tier_groups[tier]["anonymous"] > 0:
            tier_range = ""
            if tier == "platinum":
                tier_range = "$500+"
            elif tier == "gold":
                tier_range = "$50-$499"
            elif tier == "silver":
                tier_range = "$10-$49"
                
            anonymous_count = tier_groups[tier]["anonymous"]
            html += f"""        <div class="donor-card {tier}">
            <div class="name">{'Anonymous Donor' if anonymous_count == 1 else f"{anonymous_count} Anonymous Donors"}</div>
            <div class="tier">{tier.title()} Tier</div>
            <div class="tier-range">{tier_range}</div>
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

