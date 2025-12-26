from flask import Flask, request, jsonify, send_from_directory
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseUpload
import io, os, datetime, random

# ---------------- SETTINGS ----------------
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive.file']

SPREADSHEET_ID = '18U-DV8bw05-cSHHjeBlyLc9qRTEOojlw7AvS1koPWH4'
SHEET_NAME = 'SUBMISSION'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Columns in the sheet for attachments
COMPONENT_COLUMNS = ['Rent', 'Maintenance', 'Water', 'Electricity', 'Parking']
# ------------------------------------------

app = Flask(__name__, static_folder='public')

# ---------------- AUTH ----------------
def get_credentials():
    creds_file = 'client_secret.json'
    token_file = 'token.json'
    creds = None

    if os.path.exists(token_file):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds

creds = get_credentials()
sheet_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/submit_invoice', methods=['POST'])
def submit_invoice():
    try:
        ticket_id = 'TKT-' + str(random.randint(1000, 9999))
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Debug prints
        print("Form data:", request.form)
        print("Files:", request.files)

        # Form fields
        rent_start = request.form.get('rent_start', '')
        rent_end = request.form.get('rent_end', '')
        name = request.form.get('name', '')
        mobile = request.form.get('mobile', '')
        email = request.form.get('email', '')
        city = request.form.get('city', '')
        gst_type = request.form.get('gst_type', '')
        invoice_sample = request.form.get('invoice_sample', '')

        # Map uploaded files to components
        component_files = {comp: [] for comp in COMPONENT_COLUMNS}

        for comp in COMPONENT_COLUMNS:
            files = request.files.getlist(f'{comp.lower()}_files[]')  # frontend must send files with this naming
            for f in files:
                filename = f"{ticket_id}_{f.filename}"
                local_path = os.path.join(UPLOAD_FOLDER, filename)
                f.save(local_path)

                # Upload to Google Drive and get link
                file_metadata = {'name': filename}
                media = MediaIoBaseUpload(io.FileIO(local_path, 'rb'), mimetype=f.mimetype)
                file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()

                drive_link = file.get('webViewLink')
                component_files[comp].append(drive_link)

        # Prepare row: [TicketID, Rent Start, Rent End, Name, Mobile, Email, City, GST Type, RentLink, MaintenanceLink, WaterLink, ElectricityLink, ParkingLink, Timestamp]
        row = [
            ticket_id, rent_start, rent_end, name, mobile, email, city, gst_type
        ]

        # Append component links in order
        for comp in COMPONENT_COLUMNS:
            row.append(', '.join(component_files[comp]))

        # Add timestamp
        row.append(timestamp)

        # Write to Google Sheet
        sheet_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_NAME,
            valueInputOption='RAW',
            body={'values':[row]}
        ).execute()

        return jsonify({'ticket_id': ticket_id})

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
