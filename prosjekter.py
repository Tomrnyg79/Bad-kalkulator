"""
Google Sheets CRUD for lagring og henting av prosjekter.

Sheet-kolonner: id | adresse | dato | bruker | json_data
"""

import base64
import json
import uuid
import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


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
# Google Sheets – dokumenthåndtering (base64 i celler)
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 45000  # maks tegn per celle (trygg margin under 50k-grensen)


def _get_doc_worksheet():
    """Hent eller opprett 'dokumenter'-arket."""
    client = _get_client()
    url = st.secrets["google_sheets"]["url"]
    sheet = client.open_by_url(url)
    try:
        ws = sheet.worksheet("dokumenter")
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title="dokumenter", rows=1, cols=7)
        ws.append_row(["doc_id", "project_id", "doc_name", "created", "chunk", "chunks_total", "data"])
    return ws


def lagre_dokument(prosjekt_id, filnavn, pdf_bytes):
    """Lagre PDF som base64-chunks i 'dokumenter'-arket."""
    ws = _get_doc_worksheet()
    doc_id = str(uuid.uuid4())[:8]
    if not filnavn.lower().endswith(".pdf"):
        filnavn += ".pdf"
    dato = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    chunks = [encoded[i:i + _CHUNK_SIZE] for i in range(0, len(encoded), _CHUNK_SIZE)] or [""]
    total = len(chunks)
    rows = []
    for idx, chunk in enumerate(chunks):
        rows.append([doc_id, str(prosjekt_id), filnavn, dato, idx, total, chunk])
    ws.append_rows(rows, value_input_option="RAW")
    return doc_id


def hent_dokumenter(prosjekt_id):
    """List unike dokumenter for et prosjekt. Returnerer liste med dicts."""
    ws = _get_doc_worksheet()
    rader = ws.get_all_records()
    sett = {}
    pid = str(prosjekt_id)
    for rad in rader:
        if str(rad.get("project_id", "")) == pid and rad.get("chunk", 0) == 0:
            sett[rad["doc_id"]] = {
                "id": rad["doc_id"],
                "name": rad.get("doc_name", ""),
                "created": rad.get("created", ""),
            }
    # Nyeste først (basert på rekkefølge i arket, reversert)
    return list(reversed(sett.values()))


def last_ned_dokument(doc_id):
    """Hent PDF-bytes for et dokument (sett sammen chunks)."""
    ws = _get_doc_worksheet()
    rader = ws.get_all_records()
    chunks = {}
    for rad in rader:
        if str(rad.get("doc_id", "")) == str(doc_id):
            chunks[int(rad.get("chunk", 0))] = rad.get("data", "")
    if not chunks:
        raise ValueError(f"Dokument {doc_id} ikke funnet")
    encoded = "".join(chunks[i] for i in range(len(chunks)))
    return base64.b64decode(encoded)


def slett_dokument(doc_id):
    """Slett alle rader for et dokument."""
    ws = _get_doc_worksheet()
    alle = ws.get_all_values()
    # Finn rader å slette (bakfra for å unngå indeksforskyvning)
    rader_å_slette = []
    for idx, rad in enumerate(alle):
        if idx == 0:
            continue  # hopp over header
        if rad[0] == str(doc_id):
            rader_å_slette.append(idx + 1)  # gspread bruker 1-indeksering
    for rad_nr in reversed(rader_å_slette):
        ws.delete_rows(rad_nr)


def endre_dokumentnavn(doc_id, nytt_navn):
    """Endre dokumentnavn for alle chunks."""
    ws = _get_doc_worksheet()
    if not nytt_navn.lower().endswith(".pdf"):
        nytt_navn += ".pdf"
    alle = ws.get_all_values()
    for idx, rad in enumerate(alle):
        if idx == 0:
            continue
        if rad[0] == str(doc_id):
            ws.update_cell(idx + 1, 3, nytt_navn)  # kolonne 3 = doc_name
