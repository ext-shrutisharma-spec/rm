from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # <-- Import CORS
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
import io, os, datetime, random
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

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

# Enable CORS for your frontend only
CORS(app, origins=["https://rm-1-fidk.onrender.com"])

# ---------------- AUTH ----------------
def get_credentials():
    token_file = 'token.json'
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    else:
        # Create client config from environment variables
        client_config = {
            "installed": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "project_id": os.environ.get("GOOGLE_PROJECT_ID"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": os.environ.get("GOOGLE_REDIRECT_URIS").split(',')
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save token for future use
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
            files = request.files.getlist(f'{comp.lower()}_files[]')
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

        # Prepare row for Google Sheet
        row = [
            ticket_id, rent_start, rent_end, name, mobile, email, city, gst_type
        ]

        for comp in COMPONENT_COLUMNS:
            row.append(', '.join(component_files[comp]))

        row.append(timestamp)

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

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Render will set PORT
    app.run(debug=True, host='0.0.0.0', port=port)
