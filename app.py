import streamlit as st
import datetime
import re

from priser import FIRMA, MVA_SATS, FLIS, TOMRER, EPOXY_VALG
from eksport import generer_pdf, generer_excel, send_epost, generer_tekst_dokument_pdf, generer_bilde_dokument_pdf
from prosjekter import (lagre_prosjekt, hent_alle_prosjekter, last_prosjekt, sheets_er_konfigurert,
                         slett_prosjekt, lagre_dokument, hent_dokumenter, last_ned_dokument,
                         slett_dokument, endre_dokumentnavn, imap_er_konfigurert, sjekk_epost)

st.set_page_config(page_title="Baderoms kalkyle | Nygård Bad", page_icon="🛁", layout="centered")

# ---------------------------------------------------------------------------
# Innlogging
# ---------------------------------------------------------------------------
if "autentisert" not in st.session_state:
    st.session_state.autentisert = False

if not st.session_state.autentisert:
    st.markdown(
        "<h2 style='text-align:center; color:#555;'>Logg inn</h2>",
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        brukernavn = st.text_input("Brukernavn")
        passord = st.text_input("Passord", type="password")
        logg_inn = st.form_submit_button("Logg inn", use_container_width=True, type="primary")

    if logg_inn:
        try:
            if st.secrets["passwords"][brukernavn] == passord:
                st.session_state.autentisert = True
                st.session_state.bruker = brukernavn
                st.rerun()
            else:
                st.error("Feil brukernavn eller passord.")
        except (KeyError, TypeError):
            st.error("Feil brukernavn eller passord.")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar – bruker, prosjekter, logg ut
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"Innlogget som **{st.session_state.bruker}**")
    if st.button("Logg ut", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()

    # Lagre prosjekt (kun synlig på steg 5)
    if st.session_state.get("steg") == 5 and sheets_er_konfigurert():
        if st.button("Lagre prosjekt", use_container_width=True, type="primary"):
            try:
                pid = lagre_prosjekt(st.session_state.bruker)
                st.session_state["prosjekt_id"] = pid
                st.success(f"Prosjekt lagret! (ID: {pid})")
            except Exception as e:
                st.error(f"Kunne ikke lagre: {e}")

    # Sjekk e-post for nye prosjekter
    if imap_er_konfigurert():
        if st.button("Sjekk e-post", use_container_width=True):
            try:
                nye = sjekk_epost()
                if nye:
                    st.success(f"Opprettet {len(nye)} prosjekt(er): {', '.join(nye)}")
                    st.rerun()
                else:
                    st.info("Ingen nye e-poster.")
            except Exception as e:
                st.error(f"Kunne ikke sjekke e-post: {e}")

    st.divider()

    # Delte brukergrupper – brukere i samme gruppe ser hverandres prosjekter
    DELTE_BRUKERE = [{"tom", "roy"}]

    def _synlig_for(innlogget, prosjekt_bruker):
        """Sjekk om innlogget bruker skal se prosjektet til prosjekt_bruker."""
        a = innlogget.lower()
        b = prosjekt_bruker.lower()
        if a == b:
            return True
        # E-post-prosjekter er synlige for alle i en delt gruppe
        if b == "e-post":
            for gruppe in DELTE_BRUKERE:
                if a in gruppe:
                    return True
        for gruppe in DELTE_BRUKERE:
            if a in gruppe and b in gruppe:
                return True
        return False

    # Liste over lagrede prosjekter
    if sheets_er_konfigurert():
        st.markdown("#### Lagrede prosjekter")
        try:
            prosjekter = hent_alle_prosjekter()
            innlogget_bruker = st.session_state.get("bruker", "")
            prosjekter = [p for p in prosjekter if _synlig_for(innlogget_bruker, p.get("bruker", ""))]
            if not prosjekter:
                st.caption("Ingen lagrede prosjekter ennå.")
            for idx, proj in enumerate(prosjekter):
                adr = proj.get("adresse", "Ukjent")
                dato = proj.get("dato", "")
                bruker = proj.get("bruker", "")
                st.markdown(f"**{adr}**  \n{dato} – {bruker}")
                btn_a, btn_d, btn_s = st.columns(3)
                with btn_a:
                    if st.button("Åpne", key=f"open_{idx}", use_container_width=True):
                        last_prosjekt(proj)
                        st.rerun()
                with btn_d:
                    if st.button("Dok.", key=f"docs_{idx}", use_container_width=True):
                        st.session_state["prosjekt_id"] = proj.get("id", "")
                        st.session_state["dok_prosjekt_adresse"] = adr
                        st.session_state["vis_dokumenter"] = True
                        st.rerun()
                with btn_s:
                    bekreft_key = f"bekreft_slett_{idx}"
                    if st.session_state.get(bekreft_key):
                        if st.button("Bekreft?", key=f"slett2_{idx}", use_container_width=True, type="primary"):
                            try:
                                slett_prosjekt(proj.get("id", ""))
                                del st.session_state[bekreft_key]
                                st.rerun()
                            except Exception as e:
                                st.error(f"Feil: {e}")
                    else:
                        if st.button("Slett", key=f"slett_{idx}", use_container_width=True):
                            st.session_state[bekreft_key] = True
                            st.rerun()
        except Exception as e:
            st.caption(f"Kunne ikke hente prosjekter: {e}")
    else:
        st.caption("Google Sheets er ikke konfigurert. Prosjektlagring er deaktivert.")


def fmt(tall):
    return f"{tall:,.0f}".replace(",", " ")


def trygt_filnavn(tekst):
    return re.sub(r"_+", "_", re.sub(r"[^\w\-]", "_", tekst.strip())).strip("_")


# ---------------------------------------------------------------------------
# Beregninger
# ---------------------------------------------------------------------------

def p(navn, mengde, enhet, enhetspris):
    """Lag en postlinje: (navn, mengde, enhet, enhetspris, total)."""
    return (navn, mengde, enhet, enhetspris, round(mengde * enhetspris))


def beregn_flisarbeider(d):
    poster = []
    poster.append(p("Rigg/oppstart", 1, "stk", FLIS["rigg_oppstart"]))
    gulv = d.get("gulvareal", 0)
    vegg = d.get("veggareal", 0)
    lm = d.get("lopemeter", 0)
    vegg_og_gulv = d.get("flisomfang") == "Vegg og gulv"
    f_gulv = FLIS["stor_flis_faktor"] if d.get("flis_str_gulv") == "60x120" else 1.0
    f_vegg = FLIS["stor_flis_faktor"] if d.get("flis_str_vegg") == "60x120" else 1.0

    poster.append(p("Gulvstøp", gulv, "m²", FLIS["gulvstop"]))
    if "Smøremembran" in d.get("membran_gulv_type", "Smøremembran"):
        poster.append(p("Smøremembran gulv", gulv, "m²", FLIS["membran_gulv"]))

    if vegg_og_gulv:
        poster.append(p("Membran vegg", vegg, "m²", FLIS["membran_vegg"]))

    pris_gulv = FLIS["flis_gulv_base"] * f_gulv
    poster.append(p(f"Flislegging gulv ({d.get('flis_str_gulv', '60x60')})", gulv, "m²", pris_gulv))

    if vegg_og_gulv:
        pris_vegg = FLIS["flis_vegg_base"] * f_vegg
        poster.append(p(f"Flislegging vegg ({d.get('flis_str_vegg', '60x60')})", vegg, "m²", pris_vegg))
    else:
        poster.append(p("Sokkelflis", lm, "lm", FLIS["sokkelflis"]))

    dusj = d.get("areal_dusjgulv", 1.0)
    if dusj > 0:
        poster.append(p("Flislegging dusjgulv", dusj, "m²", FLIS["flis_dusj"]))

    sluk = d.get("antall_sluk", 1)
    if sluk > 1:
        poster.append(p("Tillegg ekstra sluk", sluk - 1, "stk", FLIS["ekstra_sluk"]))

    utv = d.get("utvendige_hjorner", 0)
    if utv > 0:
        if d.get("hjorne_behandling") == "Hjørnelist":
            poster.append(p("Hjørnelist utv. hjørner", utv, "stk", FLIS["hjornelist"]))
        else:
            poster.append(p("Gjæring utv. hjørner", utv, "stk", FLIS["gjaring_hjorne"]))

    nisjer = d.get("antall_nisjer", 0)
    if nisjer > 0:
        if "Gjæring" in d.get("nisje_beh", "List"):
            poster.append(p("Nisje m/gjæring", nisjer, "stk", FLIS["nisje_flis_gjaring"]))
        else:
            poster.append(p("Nisje m/list", nisjer, "stk", FLIS["nisje_flis_list"]))

    cist = d.get("antall_cisternekasser", 0)
    if cist > 0:
        cist_beh = d.get("cisternekasse_beh", "List")
        if "Gjæring" in cist_beh:
            poster.append(p("Cisternekasse m/gjæring", cist, "stk", FLIS["cisternekasse_gjaring"]))
        elif "Gips" not in cist_beh:
            poster.append(p("Cisternekasse m/list", cist, "stk", FLIS["cisternekasse_list"]))

    # Silikonering: innvendige hjørner (høyde per stk) + overgang gulv/vegg (løpemeter)
    innv = d.get("innvendige_hjorner", 4)
    hoyde = d.get("hoyde", 2.4)
    sil_hjorner = round(innv * hoyde, 2)
    sil_gulv_vegg = lm
    sil_total_lm = round(sil_hjorner + sil_gulv_vegg, 2)
    if sil_total_lm > 0:
        poster.append(p("Silikonering", sil_total_lm, "lm", FLIS["silikonering"]))

    poster.append(p("Dokumentasjon", 1, "bad", FLIS["dokumentasjon"]))

    epoxy = EPOXY_VALG.get(d.get("epoxy_valg", "Ikke inkludert"), 0)
    if epoxy > 0:
        poster.append(p("Epoxyfug", 1, "stk", epoxy))

    return poster


def beregn_tomrerarbeid(d):
    poster = []
    poster.append(p("Rigg/oppstart", 1, "stk", TOMRER["rigg_oppstart"]))
    gulv = d.get("gulvareal", 0)
    vegg = d.get("veggareal", 0)

    if d.get("isolering_vegg"):
        poster.append(p("Isolering vegg", vegg, "m²", TOMRER["isolering_standard"]))
    if d.get("isolering_tak"):
        poster.append(p("Isolering tak", gulv, "m²", TOMRER["isolering_tak"]))

    if d.get("paforing_vegg"):
        poster.append(p("Påforing / lekting vegg", vegg, "m²", TOMRER["paforing_vegg"]))

    vegg_og_gulv = d.get("flisomfang") == "Vegg og gulv"
    if vegg_og_gulv:
        poster.append(p("Montering finerplater", vegg, "m²", TOMRER["finerplater"]))
        poster.append(p("Montering våtromsplater vegg", vegg, "m²", TOMRER["vatromsplater"]))
    else:
        if d.get("finer_bak_gips"):
            poster.append(p("Finer bak gips vegg", vegg, "m²", TOMRER["finerplater"]))
        gips_vegg_total = max(vegg * TOMRER["gips_vegg"], TOMRER["min_tak"])
        poster.append(("Gips vegg", vegg, "m²", TOMRER["gips_vegg"], round(gips_vegg_total)))
    nedforing_total = max(gulv * TOMRER["nedforing_tak"], TOMRER["min_tak"])
    poster.append(("Nedforing / lekting tak", gulv, "m²", TOMRER["nedforing_tak"], round(nedforing_total)))
    gips_total = max(gulv * TOMRER["gips_tak"], TOMRER["min_tak"])
    poster.append(("Gips tak", gulv, "m²", TOMRER["gips_tak"], round(gips_total)))

    inn = d.get("antall_innerdorer", 0)
    if inn > 0:
        poster.append(p("Innerdør komplett", inn, "stk", TOMRER["innerdor"]))

    sky = d.get("antall_skyvedorer", 0)
    if sky > 0:
        poster.append(p("Skyvedør komplett", sky, "stk", TOMRER["skyvedor"]))

    lister = d.get("antall_kun_nye_lister", 0)
    if lister > 0:
        poster.append(p("Kun nye lister", lister, "stk", TOMRER["kun_nye_lister"]))

    nisjer = d.get("antall_nisjer", 0)
    if nisjer > 0:
        poster.append(p("Nisje tømrer", nisjer, "stk", TOMRER["nisje"]))

    utv = d.get("utvendige_hjorner", 0)
    if utv > 0:
        poster.append(p("Utvendige hjørner", utv, "stk", TOMRER["utvendig_hjorne"]))

    cist = d.get("antall_cisternekasser", 0)
    if cist > 0:
        cist_beh = d.get("cisternekasse_beh", "List")
        if "Gips" in cist_beh:
            poster.append(p("Cisternekasse gips/trevirke", cist, "stk", FLIS["cisternekasse_gips_trevirke"]))

    innv = d.get("innvendige_hjorner", 4)
    if innv > 4:
        ekstra = innv - 4
        poster.append(p("Ekstra innv. hjørner", ekstra, "stk", TOMRER["ekstra_innvendig_hjorne"]))

    return poster


def etasjetillegg_prosent(d):
    if d.get("bygningstype") != "Blokk / Leilighet":
        return 0
    etasje = d.get("_etasje", d.get("etasje", 1))
    heis = d.get("_heis", d.get("heis_valg", "Ja")) == "Ja"
    if etasje < 2 or heis:
        return 0
    return etasje * 5


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "steg" not in st.session_state:
    st.session_state.steg = 1

# Gjenopprett lagrede verdier for widgetfrie nøkler (navigering tilbake)
# Widgets med key= håndterer sine egne verdier, så vi gjenoppretter kun
# nøkler som ikke har en tilhørende widget på gjeldende steg.
_WIDGET_FRIE = {
    "antall_vegger", "lopemeter", "veggareal",
    "flisomfang", "flisomfang_valg", "hjorne_behandling", "hjorne_beh_valg",
    "heis_valg",
}
for _k in list(st.session_state.keys()):
    if _k.startswith("_") and not _k.startswith("__"):
        _navn = _k[1:]
        if _navn in _WIDGET_FRIE and _navn not in st.session_state:
            st.session_state[_navn] = st.session_state[_k]

STEG = ["Prosjekt", "Rommål", "Romdetaljer", "Tjeneste", "Oppsummering"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
import pathlib
_logo = pathlib.Path(__file__).parent / "unnamed.jpg"
if _logo.exists():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image(str(_logo), use_container_width=True)
st.markdown(
    "<h2 style='text-align:center; color:#555; margin-top:0'>Baderoms kalkyle</h2>",
    unsafe_allow_html=True,
)

# ===================================================================
# DOKUMENTVISNING (separat fra kalkyle-stegene)
# ===================================================================
if st.session_state.get("vis_dokumenter"):
    prosjekt_id = st.session_state.get("prosjekt_id", "")
    dok_adresse = st.session_state.get("dok_prosjekt_adresse", "Ukjent prosjekt")

    st.markdown(f"### Dokumenter – {dok_adresse}")

    if st.button("← Tilbake til kalkyle", use_container_width=False):
        st.session_state["vis_dokumenter"] = False
        st.rerun()

    st.divider()

    if not prosjekt_id:
        st.warning("Ingen prosjekt-ID funnet.")
        st.stop()

    # --- Dokumentliste (øverst) ---
    try:
        dok_liste = hent_dokumenter(prosjekt_id)
        if not dok_liste:
            st.caption("Ingen dokumenter ennå.")
        for doc in dok_liste:
            doc_id = doc["id"]
            doc_name = doc["name"]
            created = doc.get("created", "")

            st.markdown(f"**{doc_name}**  \n*{created}*")
            dk1, dk2, dk3 = st.columns(3)
            with dk1:
                try:
                    doc_bytes = last_ned_dokument(doc_id)
                    st.download_button(
                        "Last ned", doc_bytes, file_name=doc_name,
                        mime="application/pdf", key=f"dl_{doc_id}",
                        use_container_width=True,
                    )
                except Exception:
                    st.button("Last ned", key=f"dl_{doc_id}", disabled=True, use_container_width=True)
            with dk2:
                if st.button("Gi nytt navn", key=f"ren_{doc_id}", use_container_width=True):
                    st.session_state[f"renaming_{doc_id}"] = True
            with dk3:
                if st.button("Slett", key=f"del_{doc_id}", use_container_width=True):
                    try:
                        slett_dokument(doc_id)
                        st.success(f"«{doc_name}» slettet.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunne ikke slette: {e}")

            if st.session_state.get(f"renaming_{doc_id}"):
                nytt = st.text_input("Nytt navn", value=doc_name.replace(".pdf", ""), key=f"newname_{doc_id}")
                rk1, rk2 = st.columns(2)
                with rk1:
                    if st.button("Lagre navn", key=f"savename_{doc_id}", use_container_width=True):
                        try:
                            endre_dokumentnavn(doc_id, nytt)
                            del st.session_state[f"renaming_{doc_id}"]
                            st.success(f"Omdøpt til «{nytt}.pdf»")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Kunne ikke endre navn: {e}")
                with rk2:
                    if st.button("Avbryt", key=f"cancelname_{doc_id}", use_container_width=True):
                        del st.session_state[f"renaming_{doc_id}"]
                        st.rerun()

            st.divider()
    except Exception as e:
        st.error(f"Kunne ikke hente dokumenter: {e}")

    # --- Legg til nytt dokument (ekspanderbar) ---
    with st.expander("+ Legg til nytt dokument"):

        dok_type = st.radio("Type", ["Last opp fil (PDF/bilder)", "Skriv tekstdokument"],
                            horizontal=True, key="dok_type_valg")

        if dok_type == "Last opp fil (PDF/bilder)":
            dok_fil_navn = st.text_input("Dokumentnavn", value="", key="dok_fil_navn",
                                          placeholder="F.eks. Plantegning")
            opplastede_filer = st.file_uploader(
                "Last opp filer", type=["jpg", "jpeg", "png", "pdf"],
                accept_multiple_files=True, key="dok_filer",
            )
            if st.button("Lagre dokument", type="primary", key="btn_opprett_fil"):
                if not opplastede_filer:
                    st.error("Last opp minst én fil først.")
                elif not dok_fil_navn.strip():
                    st.error("Gi dokumentet et navn.")
                else:
                    try:
                        # Sjekk om det er kun én PDF-fil → lagre direkte
                        if (len(opplastede_filer) == 1
                                and opplastede_filer[0].name.lower().endswith(".pdf")):
                            pdf_bytes = opplastede_filer[0].getvalue()
                        else:
                            # Filtrer ut bilder og PDFer separat
                            bilder = []
                            pdf_deler = []
                            for f in opplastede_filer:
                                if f.name.lower().endswith(".pdf"):
                                    pdf_deler.append(f.getvalue())
                                else:
                                    bilder.append((f.name, f.getvalue()))
                            if bilder:
                                pdf_bytes = generer_bilde_dokument_pdf(dok_fil_navn, bilder)
                            elif pdf_deler:
                                pdf_bytes = pdf_deler[0]
                            else:
                                st.error("Ingen gyldige filer funnet.")
                                st.stop()
                        lagre_dokument(prosjekt_id, dok_fil_navn, pdf_bytes)
                        st.success(f"«{dok_fil_navn}» er lagret!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunne ikke lagre dokument: {e}")

        else:  # Tekstdokument
            dok_tekst_navn = st.text_input("Dokumentnavn", value="", key="dok_tekst_navn",
                                            placeholder="F.eks. Prosjektbeskrivelse")
            dok_tekst_innhold = st.text_area("Innhold", height=200, key="dok_tekst_innhold",
                                              placeholder="Skriv inn tekst her...")
            if st.button("Lagre dokument", type="primary", key="btn_opprett_tekst"):
                if not dok_tekst_innhold.strip():
                    st.error("Skriv inn tekst først.")
                elif not dok_tekst_navn.strip():
                    st.error("Gi dokumentet et navn.")
                else:
                    try:
                        pdf_bytes = generer_tekst_dokument_pdf(dok_tekst_navn, dok_tekst_innhold)
                        lagre_dokument(prosjekt_id, dok_tekst_navn, pdf_bytes)
                        st.success(f"«{dok_tekst_navn}» er opprettet!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunne ikke opprette dokument: {e}")

    st.stop()

# ===================================================================
# KALKYLE-STEG (vises kun når vis_dokumenter er False/ikke satt)
# ===================================================================
fremdrift = (st.session_state.steg - 1) / (len(STEG) - 1)
st.progress(fremdrift)
st.markdown(f"**Steg {st.session_state.steg} av {len(STEG)}: {STEG[st.session_state.steg - 1]}**")
st.divider()

# ===================================================================
# STEG 1 – Prosjekt
# ===================================================================
if st.session_state.steg == 1:
    st.subheader("Prosjektinformasjon")

    st.text_input("Prosjektadresse", placeholder="F.eks. Storgata 1, 0570 Oslo", key="adresse")

    st.radio("Bygningstype", ["Enebolig", "Blokk / Leilighet"], horizontal=True, key="bygningstype")

    if st.session_state.get("bygningstype") == "Blokk / Leilighet":
        if "etasje" not in st.session_state:
            st.session_state.etasje = 1
        st.number_input("Etasje", min_value=1, max_value=20, step=1, key="etasje")
        if st.session_state.get("etasje", 1) >= 2:
            st.radio("Er det heis i bygget?", ["Ja", "Nei"], horizontal=True, key="heis_valg")
            if st.session_state.get("heis_valg") == "Nei":
                pst = st.session_state["etasje"] * 5
                st.warning(f"Tillegg {pst}% for {st.session_state['etasje']}. etasje uten heis.")

    _, kol_h = st.columns(2)
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            if not st.session_state.get("adresse", "").strip():
                st.error("Vennligst fyll inn prosjektadressen.")
            else:
                # Lagre steg 1-verdier eksplisitt
                st.session_state["_adresse"] = st.session_state.get("adresse", "")
                st.session_state["_bygningstype"] = st.session_state.get("bygningstype", "Enebolig")
                if st.session_state.get("bygningstype") == "Blokk / Leilighet":
                    st.session_state["_etasje"] = st.session_state.get("etasje", 1)
                    st.session_state["_heis"] = st.session_state.get("heis_valg", "Ja")
                    st.session_state["_heis_valg"] = st.session_state.get("heis_valg", "Ja")
                else:
                    st.session_state["_etasje"] = 1
                    st.session_state["_heis"] = "Ja"
                    st.session_state["_heis_valg"] = "Ja"
                st.session_state.steg = 2
                st.rerun()

# ===================================================================
# STEG 2 – Rommål
# ===================================================================
elif st.session_state.steg == 2:
    st.subheader("Rommål")

    # Takhøyde
    if "hoyde" not in st.session_state:
        st.session_state.hoyde = 2.4
    st.number_input("Takhøyde (m)", 1.0, 10.0, step=0.1, format="%.2f", key="hoyde")

    # Dynamiske vegger
    if "antall_vegger" not in st.session_state:
        st.session_state.antall_vegger = 4

    st.markdown("#### Vegglengder")
    for i in range(st.session_state.antall_vegger):
        if f"vegg_{i}" not in st.session_state:
            st.session_state[f"vegg_{i}"] = 2.0
        st.number_input(
            f"Vegg {i + 1} (m)", 0.0, 50.0,
            step=0.1, format="%.2f", key=f"vegg_{i}",
        )

    k_pluss, k_minus, _ = st.columns([1, 1, 2])
    with k_pluss:
        if st.button("+ Legg til vegg", use_container_width=True):
            st.session_state.antall_vegger += 1
            st.rerun()
    with k_minus:
        if st.session_state.antall_vegger > 3:
            if st.button("- Fjern siste vegg", use_container_width=True):
                # Fjern nøkkelen for siste vegg
                siste = f"vegg_{st.session_state.antall_vegger - 1}"
                if siste in st.session_state:
                    del st.session_state[siste]
                st.session_state.antall_vegger -= 1
                st.rerun()

    h = st.session_state["hoyde"]
    lopemeter = round(sum(st.session_state.get(f"vegg_{i}", 0) for i in range(st.session_state.antall_vegger)), 2)
    veggareal = round(lopemeter * h, 2)

    st.session_state["lopemeter"] = lopemeter
    st.session_state["veggareal"] = veggareal

    st.divider()
    if "gulvareal" not in st.session_state:
        st.session_state.gulvareal = 5.0
    st.number_input("Gulvareal (m²)", 0.1, 200.0, step=0.1, format="%.2f", key="gulvareal",
                     help="Mål opp gulvarealet i rommet. For uregelmessige rom: del opp i rektangler og summer.")

    st.info(f"**Løpemeter vegg:** {lopemeter} m  |  **Veggareal:** {veggareal} m²  |  **Gulvareal:** {st.session_state['gulvareal']} m²")

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 1
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            # Lagre steg 2-verdier eksplisitt
            vegger = {f"vegg_{i}": st.session_state.get(f"vegg_{i}", 0) for i in range(st.session_state.antall_vegger)}
            for nk, val in vegger.items():
                st.session_state[f"_{nk}"] = val
            st.session_state["_antall_vegger"] = st.session_state.antall_vegger
            for nk in ["hoyde", "lopemeter", "gulvareal", "veggareal"]:
                if nk in st.session_state:
                    st.session_state[f"_{nk}"] = st.session_state[nk]
            st.session_state.steg = 3
            st.rerun()

# ===================================================================
# STEG 3 – Romdetaljer
# ===================================================================
elif st.session_state.steg == 3:
    st.subheader("Romdetaljer")

    # --- Flisvalg ---
    st.markdown("#### Flisvalg")
    st.radio("Flislegging", ["Vegg og gulv", "Kun gulv (gips på vegger)"], horizontal=True, key="flisomfang_valg")

    flisomfang = "Vegg og gulv" if "Vegg og gulv" in st.session_state.get("flisomfang_valg", "") else "Kun gulv"
    st.session_state["flisomfang"] = flisomfang

    flis_str = ["20x20", "30x30", "60x60", "60x120"]
    k1, k2 = st.columns(2)
    with k1:
        if "flis_str_gulv" not in st.session_state:
            st.session_state.flis_str_gulv = "60x60"
        st.selectbox("Flisstørrelse gulv", flis_str, key="flis_str_gulv")
    with k2:
        if flisomfang == "Vegg og gulv":
            if "flis_str_vegg" not in st.session_state:
                st.session_state.flis_str_vegg = "60x60"
            st.selectbox("Flisstørrelse vegg", flis_str, key="flis_str_vegg")
        else:
            st.markdown("&nbsp;\n\n*Sokkelflis på vegger*")

    if flisomfang == "Kun gulv":
        st.checkbox("Finer bak gips på vegg", key="finer_bak_gips")

    st.radio("Membran gulv", ["Smøremembran", "Banemembran (ikke inkl. i pris)"], horizontal=True, key="membran_gulv_type")

    if "areal_dusjgulv" not in st.session_state:
        st.session_state.areal_dusjgulv = 1.0
    st.number_input("Areal dusjgulv (m²)", 0.0, 20.0, step=0.1, format="%.1f", key="areal_dusjgulv")

    st.divider()

    # --- Sanitær ---
    st.markdown("#### Sanitær")
    if "antall_sluk" not in st.session_state:
        st.session_state.antall_sluk = 1
    st.number_input("Antall sluk", 0, 10, step=1, key="antall_sluk")
    if st.session_state.get("antall_sluk", 1) > 1:
        ekstra = st.session_state["antall_sluk"] - 1
        st.caption(f"Tillegg {fmt(ekstra * FLIS['ekstra_sluk'])} kr for {ekstra} ekstra sluk")

    st.divider()

    # --- Hjørner ---
    st.markdown("#### Hjørner")
    k1, k2 = st.columns(2)
    with k1:
        if "innvendige_hjorner" not in st.session_state:
            st.session_state.innvendige_hjorner = 4
        st.number_input("Innvendige hjørner", 0, 30, step=1, key="innvendige_hjorner")
    with k2:
        if "utvendige_hjorner" not in st.session_state:
            st.session_state.utvendige_hjorner = 0
        st.number_input("Utvendige hjørner", 0, 30, step=1, key="utvendige_hjorner")

    if st.session_state.get("utvendige_hjorner", 0) > 0:
        st.radio(
            "Behandling utvendige hjørner",
            ["Hjørnelist (1 500 kr/stk)", "Gjæring (2 500 kr/stk)"],
            horizontal=True, key="hjorne_beh_valg",
        )
        st.session_state["hjorne_behandling"] = (
            "Hjørnelist" if "Hjørnelist" in st.session_state.get("hjorne_beh_valg", "") else "Gjæring"
        )

    st.divider()

    # --- Isolering og påforing ---
    st.markdown("#### Isolering og påforing")
    k1, k2, k3 = st.columns(3)
    with k1:
        st.checkbox("Isolering vegg", key="isolering_vegg")
    with k2:
        st.checkbox("Isolering tak", key="isolering_tak")
    with k3:
        st.checkbox("Påforing / lekting vegg", key="paforing_vegg")

    st.divider()

    # --- Dører ---
    st.markdown("#### Dører")
    k1, k2 = st.columns(2)
    with k1:
        if "antall_innerdorer" not in st.session_state:
            st.session_state.antall_innerdorer = 1
        st.number_input("Innerdører", 0, 10, step=1, key="antall_innerdorer")
    with k2:
        if "antall_skyvedorer" not in st.session_state:
            st.session_state.antall_skyvedorer = 0
        st.number_input("Skyvedører", 0, 10, step=1, key="antall_skyvedorer")

    if "antall_kun_nye_lister" not in st.session_state:
        st.session_state.antall_kun_nye_lister = 0
    st.number_input("Kun nye lister", 0, 20, step=1, key="antall_kun_nye_lister")

    st.divider()

    # --- Nisjer og annet ---
    st.markdown("#### Nisjer og annet")
    k1, k2 = st.columns(2)
    with k1:
        if "antall_nisjer" not in st.session_state:
            st.session_state.antall_nisjer = 0
        st.number_input("Antall nisjer", 0, 20, step=1, key="antall_nisjer")
    with k2:
        if "antall_cisternekasser" not in st.session_state:
            st.session_state.antall_cisternekasser = 0
        st.number_input("Antall cisternekasser", 0, 10, step=1, key="antall_cisternekasser")

    if st.session_state.get("antall_nisjer", 0) > 0:
        st.radio(
            "Nisje behandling",
            ["List (3 500 kr/stk)", "Gjæring (4 500 kr/stk)"],
            horizontal=True, key="nisje_beh",
        )

    if st.session_state.get("antall_cisternekasser", 0) > 0:
        st.radio(
            "Cisternekasse behandling",
            ["List (3 500 kr/stk)", "Gjæring (4 500 kr/stk)", "Gips/trevirke (1 950 kr/stk)"],
            horizontal=True, key="cisternekasse_beh",
        )

    st.divider()

    # --- Epoxy ---
    st.markdown("#### Epoxyfug")
    if "epoxy_valg" not in st.session_state:
        st.session_state.epoxy_valg = "Ikke inkludert"
    st.selectbox("Epoxyfug", list(EPOXY_VALG.keys()), key="epoxy_valg")

    # --- Egendefinerte poster ---
    st.divider()
    st.markdown("#### Egendefinerte poster")

    if "antall_egendefinerte" not in st.session_state:
        st.session_state.antall_egendefinerte = 0

    for i in range(st.session_state.antall_egendefinerte):
        st.markdown(f"**Post {i + 1}**")
        ek1, ek2, ek3 = st.columns([1, 2, 1])
        with ek1:
            if f"ep_kat_{i}" not in st.session_state:
                st.session_state[f"ep_kat_{i}"] = "Flisarbeider"
            st.selectbox("Kategori", ["Flisarbeider", "Tømrerarbeider"], key=f"ep_kat_{i}", label_visibility="collapsed")
        with ek2:
            if f"ep_beskr_{i}" not in st.session_state:
                st.session_state[f"ep_beskr_{i}"] = ""
            st.text_input("Beskrivelse", key=f"ep_beskr_{i}", placeholder="Beskrivelse", label_visibility="collapsed")
        with ek3:
            if f"ep_pris_{i}" not in st.session_state:
                st.session_state[f"ep_pris_{i}"] = 0
            st.number_input("Pris", min_value=0, step=100, key=f"ep_pris_{i}", label_visibility="collapsed")

    ep_pluss, ep_minus, _ = st.columns([1, 1, 2])
    with ep_pluss:
        if st.button("+ Legg til post", use_container_width=True):
            st.session_state.antall_egendefinerte += 1
            st.rerun()
    with ep_minus:
        if st.session_state.antall_egendefinerte > 0:
            if st.button("- Fjern siste", use_container_width=True):
                siste_i = st.session_state.antall_egendefinerte - 1
                for pfx in ("ep_kat_", "ep_beskr_", "ep_pris_"):
                    nk = f"{pfx}{siste_i}"
                    if nk in st.session_state:
                        del st.session_state[nk]
                st.session_state.antall_egendefinerte -= 1
                st.rerun()

    # --- Nav ---
    st.divider()
    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 2
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            # Lagre alle steg 3-verdier eksplisitt så de overlever til steg 5
            for nk in [
                "flisomfang", "flisomfang_valg",
                "flis_str_gulv", "flis_str_vegg", "finer_bak_gips",
                "membran_gulv_type",
                "areal_dusjgulv", "antall_sluk",
                "innvendige_hjorner", "utvendige_hjorner",
                "hjorne_behandling", "hjorne_beh_valg",
                "isolering_vegg", "isolering_tak", "paforing_vegg",
                "antall_innerdorer", "antall_skyvedorer", "antall_kun_nye_lister",
                "antall_nisjer", "nisje_beh",
                "antall_cisternekasser", "cisternekasse_beh",
                "epoxy_valg",
                "antall_egendefinerte",
            ]:
                if nk in st.session_state:
                    st.session_state[f"_{nk}"] = st.session_state[nk]
            # Lagre egendefinerte poster
            for i in range(st.session_state.get("antall_egendefinerte", 0)):
                for pfx in ("ep_kat_", "ep_beskr_", "ep_pris_"):
                    nk = f"{pfx}{i}"
                    if nk in st.session_state:
                        st.session_state[f"_{nk}"] = st.session_state[nk]
            st.session_state.steg = 4
            st.rerun()

# ===================================================================
# STEG 4 – Velg tjeneste
# ===================================================================
elif st.session_state.steg == 4:
    st.subheader("Velg tjeneste")

    if "tjeneste" not in st.session_state:
        st.session_state.tjeneste = "Flisarbeider + tømrerarbeider"
    st.radio(
        "Hva ønsker du pris for?",
        ["Kun flisarbeider", "Kun tømrerarbeider", "Flisarbeider + tømrerarbeider"],
        key="tjeneste",
    )

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 3
            st.rerun()
    with kol_h:
        if st.button("Se kalkyle →", use_container_width=True, type="primary"):
            st.session_state["_tjeneste"] = st.session_state.get("tjeneste", "Flisarbeider + tømrerarbeider")
            st.session_state.steg = 5
            st.rerun()

# ===================================================================
# STEG 5 – Oppsummering
# ===================================================================
elif st.session_state.steg == 5:
    st.subheader("Oppsummering")

    d = dict(st.session_state)
    # Gjenopprett lagrede verdier fra steg 1 og 3 (widget-nøkler forsvinner mellom steg)
    for nk in list(d.keys()):
        if nk.startswith("_") and nk[1:] not in d:
            d[nk[1:]] = d[nk]
    tjeneste = d.get("tjeneste", "Flisarbeider + tømrerarbeider")

    st.markdown(f"**Prosjekt:** {d.get('adresse', '')}")
    st.markdown(f"**Dato:** {datetime.date.today().strftime('%d.%m.%Y')}")
    st.markdown(f"**Gulvareal:** {d.get('gulvareal', 0)} m²  |  **Veggareal:** {d.get('veggareal', 0)} m²")

    if d.get("bygningstype") == "Blokk / Leilighet":
        etinfo = f"Blokk/leilighet, {d.get('etasje', 1)}. etasje"
        if d.get("etasje", 1) >= 2:
            etinfo += f", {'heis' if d.get('heis_valg', 'Ja') == 'Ja' else 'uten heis'}"
        st.markdown(f"**Bygning:** {etinfo}")

    st.divider()

    vis_flis = tjeneste in ("Kun flisarbeider", "Flisarbeider + tømrerarbeider")
    vis_tomrer = tjeneste in ("Kun tømrerarbeider", "Flisarbeider + tømrerarbeider")

    flis_poster = beregn_flisarbeider(d) if vis_flis else []
    tomrer_poster = beregn_tomrerarbeid(d) if vis_tomrer else []

    # Legg til egendefinerte poster i riktig kategori
    for i in range(int(d.get("antall_egendefinerte", 0))):
        kat = d.get(f"ep_kat_{i}", "Flisarbeider")
        beskr = d.get(f"ep_beskr_{i}", "")
        pris = d.get(f"ep_pris_{i}", 0)
        if beskr and pris:
            post = (beskr, 1, "stk", pris, round(pris))
            if kat == "Flisarbeider" and vis_flis:
                flis_poster.append(post)
            elif kat == "Tømrerarbeider" and vis_tomrer:
                tomrer_poster.append(post)

    def vis_poster(tittel, poster):
        st.markdown(f"### {tittel}")
        k1, k2, k3, k4, k5 = st.columns([2.5, 0.7, 0.5, 0.8, 1])
        with k1:
            st.markdown("**Post**")
        with k2:
            st.markdown("**Mengde**")
        with k3:
            st.markdown("**Enhet**")
        with k4:
            st.markdown("**Enh.pris**")
        with k5:
            st.markdown("**Sum**")
        for navn, mengde, enhet, enhetspris, total in poster:
            k1, k2, k3, k4, k5 = st.columns([2.5, 0.7, 0.5, 0.8, 1])
            with k1:
                st.markdown(navn)
            with k2:
                st.markdown(f"{mengde:.2f}")
            with k3:
                st.markdown(enhet)
            with k4:
                st.markdown(f"{fmt(enhetspris)}")
            with k5:
                st.markdown(f"**{fmt(total)}**")
        seksjon_sum = sum(t for _, _, _, _, t in poster)
        st.markdown(f"**Sum {tittel.lower()}: {fmt(seksjon_sum)} kr**")
        return seksjon_sum

    sum_flis = 0
    sum_tomrer = 0

    if vis_flis and flis_poster:
        sum_flis = vis_poster("Flisarbeider", flis_poster)

    if vis_flis and vis_tomrer:
        st.divider()

    if vis_tomrer and tomrer_poster:
        sum_tomrer = vis_poster("Tømrerarbeider", tomrer_poster)
    # Totaler
    subtotal = sum_flis + sum_tomrer

    tillegg_pst = etasjetillegg_prosent(d)
    etasje_kr = round(subtotal * tillegg_pst / 100) if tillegg_pst else 0
    subtotal_total = subtotal + etasje_kr
    mva = round(subtotal_total * MVA_SATS)
    total_inkl = subtotal_total + mva

    st.divider()
    _, kol_t = st.columns([2, 2])
    with kol_t:
        if tillegg_pst > 0:
            st.markdown(f"**Sum arbeid:** {fmt(subtotal)} kr")
            st.markdown(
                f"**Tillegg {tillegg_pst}% "
                f"({d.get('etasje', 1)}. etasje, uten heis):** {fmt(etasje_kr)} kr"
            )
        st.markdown(f"**Sum eks. mva:** {fmt(subtotal_total)} kr")
        st.markdown(f"**MVA 25%:** {fmt(mva)} kr")
        st.markdown(f"### Total inkl. mva: {fmt(total_inkl)} kr")

    # Eksportdata
    eksport_data = {
        "adresse": d.get("adresse", ""),
        "dato": datetime.date.today().strftime("%d.%m.%Y"),
        "gulvareal": d.get("gulvareal", 0),
        "veggareal": d.get("veggareal", 0),
        "bygningstype": d.get("bygningstype", "Enebolig"),
        "etasje": d.get("etasje", 1),
        "heis": d.get("heis_valg", "Ja") == "Ja",
        "tjeneste": tjeneste,
        "flis_poster": flis_poster,
        "tomrer_poster": tomrer_poster,
        "tillegg_pst": tillegg_pst,
        "etasje_tillegg": etasje_kr,
        "subtotal": subtotal_total,
        "mva": mva,
        "total_inkl": total_inkl,
    }

    st.divider()
    st.subheader("Eksporter kalkyle")
    filnavn = f"kalkyle_{trygt_filnavn(d.get('adresse', 'bad'))}_{datetime.date.today()}"

    k1, k2 = st.columns(2)
    with k1:
        st.download_button(
            "Last ned PDF", generer_pdf(eksport_data),
            f"{filnavn}.pdf", "application/pdf", use_container_width=True,
        )
    with k2:
        st.download_button(
            "Last ned Excel", generer_excel(eksport_data),
            f"{filnavn}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # --- E-post ---
    st.divider()
    st.subheader("Send på e-post")

    har_smtp = hasattr(st, "secrets") and "smtp" in st.secrets
    if not har_smtp:
        st.warning("E-post er ikke konfigurert. Legg til SMTP-innstillinger i .streamlit/secrets.toml")
    else:
        # Hurtigknapper
        st.markdown("**Hurtigsending:**")
        k_chr, k_mar = st.columns(2)
        with k_chr:
            send_christian = st.button("Send til Christian", use_container_width=True)
        with k_mar:
            send_mariann = st.button("Send til Mari-ann", use_container_width=True)

        if send_christian or send_mariann:
            hurtig_mottaker = "christian@sostreneamundsen.no" if send_christian else "ma@sostreneamundsen.no"
            hurtig_navn = "Christian" if send_christian else "Mari-ann"
            try:
                smtp_config = {
                    "host": st.secrets["smtp"]["host"],
                    "port": int(st.secrets["smtp"]["port"]),
                    "bruker": st.secrets["smtp"]["bruker"],
                    "passord": st.secrets["smtp"]["passord"],
                }
                emne = f"Baderoms kalkyle – {d.get('adresse', '')}"
                brodtekst = (
                    f"Hei,\n\n"
                    f"Vedlagt finner du baderoms kalkyle for {d.get('adresse', '')}.\n"
                    f"Total inkl. mva: {fmt(total_inkl)} kr\n\n"
                    f"Med vennlig hilsen\n{FIRMA['navn']}\n{FIRMA['telefon']}\n{FIRMA['epost']}"
                )
                vedlegg_liste = [(f"{filnavn}.pdf", generer_pdf(eksport_data), "application/pdf")]
                send_epost(hurtig_mottaker, emne, brodtekst, vedlegg_liste, smtp_config)
                st.success(f"Kalkyle sendt til {hurtig_navn} ({hurtig_mottaker})!")
            except Exception as e:
                st.error(f"Kunne ikke sende: {e}")

        st.divider()
        st.markdown("**Eller send til annen mottaker:**")
        epost_mottaker = st.text_input("Mottakers e-postadresse", key="epost_mottaker",
                                        placeholder="kunde@eksempel.no")
        epost_kopi = st.text_input("Kopi til (valgfritt)", key="epost_kopi",
                                    placeholder="din@epost.no")

        vedlegg_valg = st.multiselect("Vedlegg", ["PDF", "Excel"], default=["PDF"], key="vedlegg_valg")

        if st.button("Send kalkyle på e-post", use_container_width=True, type="primary"):
            if not epost_mottaker or "@" not in epost_mottaker:
                st.error("Vennligst fyll inn en gyldig e-postadresse.")
            else:
                try:
                    smtp_config = {
                        "host": st.secrets["smtp"]["host"],
                        "port": int(st.secrets["smtp"]["port"]),
                        "bruker": st.secrets["smtp"]["bruker"],
                        "passord": st.secrets["smtp"]["passord"],
                    }

                    vedlegg_liste = []
                    if "PDF" in vedlegg_valg:
                        vedlegg_liste.append((f"{filnavn}.pdf", generer_pdf(eksport_data), "application/pdf"))
                    if "Excel" in vedlegg_valg:
                        vedlegg_liste.append((f"{filnavn}.xlsx", generer_excel(eksport_data),
                                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))

                    emne = f"Baderoms kalkyle – {d.get('adresse', '')}"
                    brodtekst = (
                        f"Hei,\n\n"
                        f"Vedlagt finner du baderoms kalkyle for {d.get('adresse', '')}.\n"
                        f"Total inkl. mva: {fmt(total_inkl)} kr\n\n"
                        f"Med vennlig hilsen\n{FIRMA['navn']}\n{FIRMA['telefon']}\n{FIRMA['epost']}"
                    )

                    mottakere = epost_mottaker
                    send_epost(mottakere, emne, brodtekst, vedlegg_liste, smtp_config)

                    if epost_kopi and "@" in epost_kopi:
                        send_epost(epost_kopi, emne, brodtekst, vedlegg_liste, smtp_config)

                    st.success(f"Kalkyle sendt til {epost_mottaker}!")
                except Exception as e:
                    st.error(f"Kunne ikke sende e-post: {e}")

    st.divider()
    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 4
            st.rerun()
    with kol_h:
        if st.button("Ny kalkyle", use_container_width=True, type="primary"):
            autentisert = st.session_state.get("autentisert")
            bruker = st.session_state.get("bruker")
            for nk in list(st.session_state.keys()):
                del st.session_state[nk]
            st.session_state.autentisert = autentisert
            st.session_state.bruker = bruker
            st.rerun()
