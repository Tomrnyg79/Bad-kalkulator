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


def oppdater_prosjekt(prosjekt_id, bruker):
    """Oppdater et eksisterende prosjekt med gjeldende session state."""
    ws = _get_worksheet()
    alle = ws.get_all_values()
    for idx, rad in enumerate(alle):
        if idx == 0:
            continue
        if rad[0] == str(prosjekt_id):
            adresse = st.session_state.get("_adresse", st.session_state.get("adresse", "Ukjent"))
            dato = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            json_data = _session_state_til_json()
            ws.update(f"A{idx+1}:E{idx+1}", [[str(prosjekt_id), adresse, dato, bruker, json_data]])
            return prosjekt_id
    # Hvis prosjektet ikke finnes, opprett nytt
    return lagre_prosjekt(bruker)


def slett_prosjekt(prosjekt_id):
    """Slett et prosjekt og tilhørende dokumenter fra Google Sheets."""
    # Slett prosjektraden
    ws = _get_worksheet()
    alle = ws.get_all_values()
    for idx, rad in enumerate(alle):
        if idx == 0:
            continue
        if rad[0] == str(prosjekt_id):
            ws.delete_rows(idx + 1)
            break
    # Slett tilhørende dokumenter
    try:
        dws = _get_doc_worksheet()
        dok_alle = dws.get_all_values()
        rader_å_slette = []
        for idx, rad in enumerate(dok_alle):
            if idx == 0:
                continue
            if len(rad) > 1 and rad[1] == str(prosjekt_id):
                rader_å_slette.append(idx + 1)
        for rad_nr in reversed(rader_å_slette):
            dws.delete_rows(rad_nr)
    except Exception:
        pass  # OK om dokumenter-arket ikke finnes ennå


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


# ---------------------------------------------------------------------------
# IMAP – hent prosjekter fra e-post
# ---------------------------------------------------------------------------

import imaplib
import email as email_lib
from email.header import decode_header


def _decode_header_value(val):
    """Dekod e-post header-verdi (kan være encoded)."""
    if val is None:
        return ""
    decoded_parts = decode_header(val)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result


def _rens_brodtekst(tekst):
    """Fjern typiske videresendings-headere fra brødtekst."""
    linjer = tekst.splitlines()
    rensede = []
    hopp_over = False
    for linje in linjer:
        stripped = linje.strip()
        # Hopp over videresendings-header-linjer
        if stripped.startswith("---------- Forwarded message") or stripped.startswith("---------- Videresendt melding"):
            hopp_over = True
            continue
        if hopp_over:
            # Hopp over From:/To:/Date:/Subject:-linjer etter forwarded header
            if stripped and ":" in stripped[:20]:
                lav = stripped.lower()
                if any(lav.startswith(p) for p in ["from:", "to:", "date:", "subject:", "fra:", "til:", "dato:", "emne:", "sent:", "cc:"]):
                    continue
            hopp_over = False
        rensede.append(linje)
    return "\n".join(rensede).strip()


def _hent_epost_tekst(msg):
    """Hent ren tekst fra e-postmelding."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def _hent_pdf_vedlegg(msg):
    """Hent alle PDF-vedlegg. Returnerer liste med (filnavn, bytes)."""
    vedlegg = []
    for part in msg.walk():
        cd = part.get("Content-Disposition", "")
        if "attachment" not in cd and "inline" not in cd:
            continue
        filnavn = part.get_filename()
        if filnavn:
            filnavn = _decode_header_value(filnavn)
        if not filnavn:
            continue
        if filnavn.lower().endswith(".pdf"):
            data = part.get_payload(decode=True)
            if data:
                vedlegg.append((filnavn, data))
    return vedlegg


def imap_er_konfigurert():
    """Sjekk om IMAP er konfigurert i secrets."""
    try:
        return "imap" in st.secrets and "host" in st.secrets["imap"]
    except Exception:
        return False


def sjekk_epost():
    """Sjekk innboks for nye e-poster og opprett prosjekter.

    Returnerer liste med opprettede prosjekt-adresser.
    """
    cfg = st.secrets["imap"]
    opprettede = []

    mail = imaplib.IMAP4_SSL(cfg["host"], int(cfg.get("port", 993)))
    try:
        mail.login(cfg["bruker"], cfg["passord"])
        mail.select("INBOX")

        _, meldinger = mail.search(None, "UNSEEN")
        for num in meldinger[0].split():
            if not num:
                continue
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email_lib.message_from_bytes(raw)

            # Emne = prosjektadresse
            emne = _decode_header_value(msg.get("Subject", ""))
            # Fjern "Fwd:", "Vs:", "Re:" etc.
            adresse = emne
            for prefiks in ["Fwd:", "FWD:", "Vs:", "VS:", "Re:", "RE:", "Sv:", "SV:"]:
                if adresse.startswith(prefiks):
                    adresse = adresse[len(prefiks):]
            adresse = adresse.strip()
            if not adresse:
                adresse = "Ukjent adresse"

            # Brødtekst = prosjektbeskrivelse
            brodtekst = _hent_epost_tekst(msg)
            brodtekst = _rens_brodtekst(brodtekst)

            # PDF-vedlegg
            vedlegg = _hent_pdf_vedlegg(msg)

            # Opprett prosjekt
            ws = _get_worksheet()
            prosjekt_id = str(uuid.uuid4())[:8]
            dato = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            json_data = json.dumps({"_adresse": adresse}, ensure_ascii=False)
            ws.append_row([prosjekt_id, adresse, dato, "e-post", json_data])

            # Lagre brødtekst som tekstdokument
            if brodtekst.strip():
                from eksport import generer_tekst_dokument_pdf
                pdf_bytes = generer_tekst_dokument_pdf("Prosjektbeskrivelse", brodtekst)
                lagre_dokument(prosjekt_id, "Prosjektbeskrivelse", pdf_bytes)

            # Lagre PDF-vedlegg som dokumenter
            for filnavn, pdf_data in vedlegg:
                navn = filnavn.replace(".pdf", "").replace(".PDF", "")
                lagre_dokument(prosjekt_id, navn, pdf_data)

            # Marker som lest
            mail.store(num, "+FLAGS", "\\Seen")
            opprettede.append(adresse)
    finally:
        mail.logout()

    return opprettede
