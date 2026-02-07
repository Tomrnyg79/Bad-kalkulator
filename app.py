import streamlit as st
import datetime
import re

from priser import FIRMA, MVA_SATS, FLIS, TOMRER, EPOXY_VALG
from eksport import generer_pdf, generer_excel, send_epost

st.set_page_config(page_title="Baderoms kalkyle | Nygård Bad", page_icon="🛁", layout="centered")


def fmt(tall):
    return f"{tall:,.0f}".replace(",", " ")


def trygt_filnavn(tekst):
    return re.sub(r"_+", "_", re.sub(r"[^\w\-]", "_", tekst.strip())).strip("_")


# ---------------------------------------------------------------------------
# Beregninger
# ---------------------------------------------------------------------------

def beregn_flisarbeider(d):
    poster = []
    gulv = d.get("gulvareal", 0)
    vegg = d.get("veggareal", 0)
    lm = d.get("lopemeter", 0)
    vegg_og_gulv = d.get("flisomfang") == "Vegg og gulv"
    f_gulv = FLIS["stor_flis_faktor"] if d.get("flis_str_gulv") == "60x120" else 1.0
    f_vegg = FLIS["stor_flis_faktor"] if d.get("flis_str_vegg") == "60x120" else 1.0

    poster.append(("Gulvstøp", round(gulv * FLIS["gulvstop"])))
    poster.append(("Membran gulv", round(gulv * FLIS["membran_gulv"])))

    if vegg_og_gulv:
        poster.append(("Membran vegg", round(vegg * FLIS["membran_vegg"])))

    poster.append((f"Flislegging gulv ({d.get('flis_str_gulv', '60x60')})",
                    round(gulv * FLIS["flis_gulv_base"] * f_gulv)))

    if vegg_og_gulv:
        poster.append((f"Flislegging vegg ({d.get('flis_str_vegg', '60x60')})",
                        round(vegg * FLIS["flis_vegg_base"] * f_vegg)))
    else:
        poster.append(("Sokkelflis", round(lm * FLIS["sokkelflis"])))

    dusj = d.get("areal_dusjgulv", 1.0)
    if dusj > 0:
        poster.append(("Flislegging dusjgulv", round(dusj * FLIS["flis_dusj"])))

    sluk = d.get("antall_sluk", 1)
    if sluk > 1:
        poster.append((f"Tillegg ekstra sluk ({sluk - 1} stk)", (sluk - 1) * FLIS["ekstra_sluk"]))

    utv = d.get("utvendige_hjorner", 0)
    if utv > 0:
        if d.get("hjorne_behandling") == "Hjørnelist":
            poster.append((f"Hjørnelist ({utv} stk)", utv * FLIS["hjornelist"]))
        else:
            poster.append((f"Gjæring utv. hjørner ({utv} stk)", utv * FLIS["gjaring_hjorne"]))

    nisjer = d.get("antall_nisjer", 0)
    if nisjer > 0:
        poster.append((f"Nisje flisarbeid ({nisjer} stk)", nisjer * FLIS["nisje_flis"]))

    cist = d.get("antall_cisternekasser", 0)
    if cist > 0:
        poster.append((f"Cisternekasse ({cist} stk)", cist * FLIS["cisternekasse"]))

    poster.append(("Dokumentasjon", FLIS["dokumentasjon"]))

    epoxy = EPOXY_VALG.get(d.get("epoxy_valg", "Ikke inkludert"), 0)
    if epoxy > 0:
        poster.append(("Epoxyfug", epoxy))

    return poster


def beregn_tomrerarbeid(d):
    poster = []
    gulv = d.get("gulvareal", 0)
    vegg = d.get("veggareal", 0)

    if d.get("isolering_vegg"):
        poster.append(("Isolering vegg", round(vegg * TOMRER["isolering_standard"])))
    if d.get("isolering_tak"):
        poster.append(("Isolering tak", round(gulv * TOMRER["isolering_tak"])))

    poster.append(("Påforing / lekting vegg", round(vegg * TOMRER["paforing_vegg"])))
    poster.append(("Montering finerplater", round(vegg * TOMRER["finerplater"])))
    poster.append(("Montering våtromsplater vegg", round(vegg * TOMRER["vatromsplater"])))
    poster.append(("Nedforing / lekting tak", round(gulv * TOMRER["nedforing_tak"])))
    poster.append(("Gips tak", round(gulv * TOMRER["gips_tak"])))

    inn = d.get("antall_innerdorer", 0)
    if inn > 0:
        poster.append((f"Innerdør komplett ({inn} stk)", inn * TOMRER["innerdor"]))

    sky = d.get("antall_skyvedorer", 0)
    if sky > 0:
        poster.append((f"Skyvedør komplett ({sky} stk)", sky * TOMRER["skyvedor"]))

    nisjer = d.get("antall_nisjer", 0)
    if nisjer > 0:
        poster.append((f"Nisje tømrer ({nisjer} stk)", nisjer * TOMRER["nisje"]))

    utv = d.get("utvendige_hjorner", 0)
    if utv > 0:
        poster.append((f"Utvendige hjørner ({utv} stk)", utv * TOMRER["utvendig_hjorne"]))

    innv = d.get("innvendige_hjorner", 4)
    if innv > 4:
        ekstra = innv - 4
        poster.append((f"Ekstra innv. hjørner ({ekstra} stk)", ekstra * TOMRER["ekstra_innvendig_hjorne"]))

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

STEG = ["Prosjekt", "Rommål", "Romdetaljer", "Tjeneste", "Oppsummering"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    "<h1 style='text-align:center; font-size:2.8em; margin-bottom:0'>Nygård Bad</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<h2 style='text-align:center; color:#555; margin-top:0'>Baderoms kalkyle</h2>",
    unsafe_allow_html=True,
)

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
        st.number_input("Etasje", min_value=1, max_value=20, value=1, step=1, key="etasje")
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
                # Lagre etasje-info eksplisitt for beregning
                if st.session_state.get("bygningstype") == "Blokk / Leilighet":
                    st.session_state["_etasje"] = st.session_state.get("etasje", 1)
                    st.session_state["_heis"] = st.session_state.get("heis_valg", "Ja")
                else:
                    st.session_state["_etasje"] = 1
                    st.session_state["_heis"] = "Ja"
                st.session_state.steg = 2
                st.rerun()

# ===================================================================
# STEG 2 – Rommål
# ===================================================================
elif st.session_state.steg == 2:
    st.subheader("Rommål")

    k1, k2, k3 = st.columns(3)
    with k1:
        st.number_input("Bredde (m)", 0.1, 50.0, 2.0, 0.1, "%.2f", key="bredde")
    with k2:
        st.number_input("Lengde (m)", 0.1, 50.0, 2.5, 0.1, "%.2f", key="lengde")
    with k3:
        st.number_input("Høyde (m)", 1.0, 10.0, 2.4, 0.1, "%.2f", key="hoyde")

    b = st.session_state["bredde"]
    l = st.session_state["lengde"]
    h = st.session_state["hoyde"]
    std_lm = round((b + l) * 2, 2)

    st.number_input(
        "Løpemeter vegg", 0.1, 200.0, std_lm, 0.1, "%.2f", key="lopemeter",
        help="Rektangulært rom = (bredde + lengde) × 2. Juster for uregelmessige rom.",
    )

    lm = st.session_state["lopemeter"]
    gulvareal = round(b * l, 2)
    veggareal = round(lm * h, 2)
    st.session_state["gulvareal"] = gulvareal
    st.session_state["veggareal"] = veggareal

    st.info(f"**Gulvareal:** {gulvareal} m²  |  **Veggareal:** {veggareal} m²")

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 1
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
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
        st.selectbox("Flisstørrelse gulv", flis_str, index=2, key="flis_str_gulv")
    with k2:
        if flisomfang == "Vegg og gulv":
            st.selectbox("Flisstørrelse vegg", flis_str, index=2, key="flis_str_vegg")
        else:
            st.markdown("&nbsp;\n\n*Sokkelflis på vegger*")

    st.number_input("Areal dusjgulv (m²)", 0.0, 20.0, 1.0, 0.1, "%.1f", key="areal_dusjgulv")

    st.divider()

    # --- Sanitær ---
    st.markdown("#### Sanitær")
    st.number_input("Antall sluk", 1, 10, 1, 1, key="antall_sluk")
    if st.session_state.get("antall_sluk", 1) > 1:
        ekstra = st.session_state["antall_sluk"] - 1
        st.caption(f"Tillegg {fmt(ekstra * FLIS['ekstra_sluk'])} kr for {ekstra} ekstra sluk")

    st.divider()

    # --- Hjørner ---
    st.markdown("#### Hjørner")
    k1, k2 = st.columns(2)
    with k1:
        st.number_input("Innvendige hjørner", 0, 30, 4, 1, key="innvendige_hjorner")
    with k2:
        st.number_input("Utvendige hjørner", 0, 30, 0, 1, key="utvendige_hjorner")

    if st.session_state.get("utvendige_hjorner", 0) > 0:
        st.radio(
            "Behandling utvendige hjørner",
            ["Hjørnelist (1 500 kr/stk)", "Gjæring (2 000 kr/stk)"],
            horizontal=True, key="hjorne_beh_valg",
        )
        st.session_state["hjorne_behandling"] = (
            "Hjørnelist" if "Hjørnelist" in st.session_state.get("hjorne_beh_valg", "") else "Gjæring"
        )

    st.divider()

    # --- Isolering ---
    st.markdown("#### Isolering")
    k1, k2 = st.columns(2)
    with k1:
        st.checkbox("Isolering vegg", value=False, key="isolering_vegg")
    with k2:
        st.checkbox("Isolering tak", value=False, key="isolering_tak")

    st.divider()

    # --- Dører ---
    st.markdown("#### Dører")
    k1, k2 = st.columns(2)
    with k1:
        st.number_input("Innerdører", 0, 10, 1, 1, key="antall_innerdorer")
    with k2:
        st.number_input("Skyvedører", 0, 10, 0, 1, key="antall_skyvedorer")

    st.divider()

    # --- Nisjer og annet ---
    st.markdown("#### Nisjer og annet")
    k1, k2 = st.columns(2)
    with k1:
        st.number_input("Antall nisjer", 0, 20, 0, 1, key="antall_nisjer")
    with k2:
        st.number_input("Antall cisternekasser", 0, 10, 0, 1, key="antall_cisternekasser")

    st.divider()

    # --- Epoxy ---
    st.markdown("#### Epoxyfug")
    st.selectbox("Epoxyfug", list(EPOXY_VALG.keys()), index=0, key="epoxy_valg")

    # --- Nav ---
    st.divider()
    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 2
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            st.session_state.steg = 4
            st.rerun()

# ===================================================================
# STEG 4 – Velg tjeneste
# ===================================================================
elif st.session_state.steg == 4:
    st.subheader("Velg tjeneste")

    st.radio(
        "Hva ønsker du pris for?",
        ["Kun flisarbeider", "Kun tømrerarbeider", "Flisarbeider + tømrerarbeider"],
        index=2,
        key="tjeneste",
    )

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 3
            st.rerun()
    with kol_h:
        if st.button("Se kalkyle →", use_container_width=True, type="primary"):
            st.session_state.steg = 5
            st.rerun()

# ===================================================================
# STEG 5 – Oppsummering
# ===================================================================
elif st.session_state.steg == 5:
    st.subheader("Oppsummering")

    d = dict(st.session_state)
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

    if vis_flis and flis_poster:
        st.markdown("### Flisarbeider")
        for navn, total in flis_poster:
            k1, k2 = st.columns([3, 1])
            with k1:
                st.markdown(navn)
            with k2:
                st.markdown(f"**{fmt(total)} kr**")
        sum_flis = sum(t for _, t in flis_poster)
        st.markdown(f"**Sum flisarbeider: {fmt(sum_flis)} kr**")

    if vis_flis and vis_tomrer:
        st.divider()

    if vis_tomrer and tomrer_poster:
        st.markdown("### Tømrerarbeider")
        for navn, total in tomrer_poster:
            k1, k2 = st.columns([3, 1])
            with k1:
                st.markdown(navn)
            with k2:
                st.markdown(f"**{fmt(total)} kr**")
        sum_tomrer = sum(t for _, t in tomrer_poster)
        st.markdown(f"**Sum tømrerarbeider: {fmt(sum_tomrer)} kr**")

    # Totaler
    subtotal = sum(t for _, t in flis_poster) + sum(t for _, t in tomrer_poster)

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
            for nk in list(st.session_state.keys()):
                del st.session_state[nk]
            st.rerun()
