"""
Google Sheets CRUD for lagring og henting av prosjekter.

Sheet-kolonner: id | adresse | dato | bruker | json_data
"""

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
