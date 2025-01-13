import os

def generate_directory(badgefile):
  # Get all attendees and sort by family name, then given name
  attendees = sorted(badgefile.attendees(), 
                    key=lambda x: (x.info()["name_family"].lower(), x.info()["name_given"].lower()))
  html = """
  <html>
  <head>
    <title>Attendee Directory</title>
    <style>
      body { font-family: sans-serif; }
      table { border-collapse: collapse; width: 100%; }
      th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
      th { background-color: #f2f2f2; }
      tr:hover { background-color: #f5f5f5; }
    </style>
  </head>
  <body>
    <h1>Attendee Directory</h1>
    <table>
      <tr>
        <th>Name</th>
        <th>Phone</th>
        <th>Email</th>
      </tr>
  """

  for attendee in attendees:
    info = attendee.info()
    html += f"""
      <tr>
        <td><strong>{info["name_family"]}, {info["name_given"]}</strong></td>
        <td>{info.get("phone_canonical", "")}</td>
        <td>{info.get("email", "")}</td>
      </tr>
    """

  html += """
    </table>
  </body>
  </html>
  """

  # Write the HTML file
  os.makedirs("artifacts", exist_ok=True)
  with open("artifacts/directory.html", "w") as f:
    f.write(html)
