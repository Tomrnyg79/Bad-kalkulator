"""
Google Sheets CRUD for lagring og henting av prosjekter.

Sheet-kolonner: id | adresse | dato | bruker | json_data
"""

import io
import json
import uuid
import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def _get_client():
    """Opprett gspread-klient fra secrets (cachet per sesjon)."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_worksheet():
    """Hent worksheet fra konfigurert Google Sheet."""
    client = _get_client()
    url = st.secrets["google_sheets"]["url"]
    sheet = client.open_by_url(url)
    ws = sheet.sheet1
    # Opprett header-rad om arket er tomt
    if ws.row_count == 0 or not ws.row_values(1):
        ws.append_row(["id", "adresse", "dato", "bruker", "json_data"])
    return ws


def _session_state_til_json():
    """Serialiser alle _-prefiks-nøkler fra session state til JSON."""
    data = {}
    for key, val in st.session_state.items():
        if key.startswith("_"):
            try:
                json.dumps(val)
                data[key] = val
            except (TypeError, ValueError):
                data[key] = str(val)
    return json.dumps(data, ensure_ascii=False)


def lagre_prosjekt(bruker):
    """Lagre gjeldende kalkyle som ny rad i Google Sheet."""
    ws = _get_worksheet()
    prosjekt_id = str(uuid.uuid4())[:8]
    adresse = st.session_state.get("_adresse", st.session_state.get("adresse", "Ukjent"))
    dato = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    json_data = _session_state_til_json()
    ws.append_row([prosjekt_id, adresse, dato, bruker, json_data])
    return prosjekt_id


def hent_alle_prosjekter():
    """Hent alle lagrede prosjekter. Returnerer liste med dicts, nyeste først."""
    ws = _get_worksheet()
    rader = ws.get_all_records()
    rader.reverse()
    return rader


def last_prosjekt(prosjekt):
    """Gjenopprett session state fra et lagret prosjekt."""
    json_data = prosjekt.get("json_data", "{}")
    data = json.loads(json_data)

    # Bevar auth-nøkler
    autentisert = st.session_state.get("autentisert")
    bruker = st.session_state.get("bruker")

    # Slett alle eksisterende nøkler unntatt auth
    for key in list(st.session_state.keys()):
        if key not in ("autentisert", "bruker"):
            del st.session_state[key]

    # Gjenopprett lagrede verdier
    for key, val in data.items():
        st.session_state[key] = val

    # Sett også widget-nøklene (uten _) slik at steg 5 finner dem
    for key, val in data.items():
        if key.startswith("_"):
            st.session_state[key[1:]] = val

    # Gjenopprett auth
    st.session_state["autentisert"] = autentisert
    st.session_state["bruker"] = bruker

    # Sett prosjekt-ID for dokumenthåndtering
    st.session_state["prosjekt_id"] = prosjekt.get("id", "")

    # Gå til oppsummering
    st.session_state["steg"] = 5


def sheets_er_konfigurert():
    """Sjekk om Google Sheets er konfigurert i secrets."""
    try:
        return (
            "gcp_service_account" in st.secrets
            and "google_sheets" in st.secrets
            and "url" in st.secrets["google_sheets"]
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Google Drive – dokumenthåndtering
# ---------------------------------------------------------------------------

_ROOT_FOLDER_NAME = "Bad-kalkulator dokumenter"


@st.cache_resource
def _get_drive_service():
    """Bygg Google Drive API-klient fra eksisterende credentials."""
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_or_create_folder(name, parent_id=None):
    """Finn eksisterende mappe eller opprett ny. Returnerer mappe-ID."""
    service = _get_drive_service()
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _get_project_folder(prosjekt_id):
    """Hent eller opprett prosjektmappe under rotmappen."""
    root_id = _get_or_create_folder(_ROOT_FOLDER_NAME)
    return _get_or_create_folder(f"proj_{prosjekt_id}", parent_id=root_id)


def lagre_dokument(prosjekt_id, filnavn, pdf_bytes):
    """Last opp en PDF til prosjektets Drive-mappe."""
    service = _get_drive_service()
    folder_id = _get_project_folder(prosjekt_id)
    if not filnavn.lower().endswith(".pdf"):
        filnavn += ".pdf"
    metadata = {"name": filnavn, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()
    return uploaded["id"]


def hent_dokumenter(prosjekt_id):
    """List alle dokumenter i prosjektmappen. Returnerer liste med dicts."""
    service = _get_drive_service()
    folder_id = _get_project_folder(prosjekt_id)
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields="files(id, name, createdTime)",
        orderBy="createdTime desc",
    ).execute()
    return results.get("files", [])


def last_ned_dokument(file_id):
    """Last ned filinnhold fra Drive. Returnerer bytes."""
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def slett_dokument(file_id):
    """Slett en fil fra Drive."""
    service = _get_drive_service()
    service.files().delete(fileId=file_id).execute()


def endre_dokumentnavn(file_id, nytt_navn):
    """Endre filnavn i Drive."""
    service = _get_drive_service()
    if not nytt_navn.lower().endswith(".pdf"):
        nytt_navn += ".pdf"
    service.files().update(fileId=file_id, body={"name": nytt_navn}).execute()
