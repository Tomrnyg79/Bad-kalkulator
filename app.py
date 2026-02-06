import streamlit as st
import datetime
import re

from priser import FIRMA, MVA_SATS, FLISARBEIDER, EPOXY_VALG
from eksport import generer_pdf, generer_excel

# ---------------------------------------------------------------------------
# Sidekonfigurasjon
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Bad-Kalkulator | Nygård Bad", page_icon="🛁", layout="centered")

# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------

def fmt(tall):
    return f"{tall:,.0f}".replace(",", " ")


def trygt_filnavn(tekst):
    return re.sub(r"[^\w\-]", "_", tekst.strip())


# ---------------------------------------------------------------------------
# Session-state initialisering
# ---------------------------------------------------------------------------
if "steg" not in st.session_state:
    st.session_state.steg = 1

STEG_NAVN = ["Prosjekt", "Rommål", "Tjeneste", "Detaljer", "Oppsummering"]

# ---------------------------------------------------------------------------
# Header og fremdrift
# ---------------------------------------------------------------------------
st.title("🛁 Bad-Kalkulator")
st.caption(FIRMA["navn"])

fremdrift = (st.session_state.steg - 1) / (len(STEG_NAVN) - 1)
st.progress(fremdrift)
st.markdown(
    f"**Steg {st.session_state.steg} av {len(STEG_NAVN)}: "
    f"{STEG_NAVN[st.session_state.steg - 1]}**"
)
st.divider()

# ===================================================================
# STEG 1 – Prosjektadresse
# ===================================================================
if st.session_state.steg == 1:
    st.subheader("Prosjektinformasjon")

    adresse = st.text_input(
        "Prosjektadresse",
        value=st.session_state.get("adresse", ""),
        placeholder="F.eks. Storgata 1, 0570 Oslo",
    )

    col_l, col_r = st.columns(2)
    with col_r:
        if st.button("Neste →", use_container_width=True, type="primary"):
            if adresse.strip():
                st.session_state.adresse = adresse.strip()
                st.session_state.steg = 2
                st.rerun()
            else:
                st.error("Vennligst fyll inn prosjektadressen.")

# ===================================================================
# STEG 2 – Rommål
# ===================================================================
elif st.session_state.steg == 2:
    st.subheader("Rommål")

    kol1, kol2, kol3 = st.columns(3)
    with kol1:
        bredde = st.number_input(
            "Bredde (m)", min_value=0.1, max_value=50.0,
            value=st.session_state.get("bredde", 2.0),
            step=0.1, format="%.2f",
        )
    with kol2:
        lengde = st.number_input(
            "Lengde (m)", min_value=0.1, max_value=50.0,
            value=st.session_state.get("lengde", 2.5),
            step=0.1, format="%.2f",
        )
    with kol3:
        hoyde = st.number_input(
            "Høyde (m)", min_value=1.0, max_value=10.0,
            value=st.session_state.get("hoyde", 2.4),
            step=0.1, format="%.2f",
        )

    standard_lopemeter = round((bredde + lengde) * 2, 2)
    lopemeter = st.number_input(
        "Løpemeter vegg",
        min_value=0.1, max_value=200.0,
        value=st.session_state.get("lopemeter", standard_lopemeter),
        step=0.1, format="%.2f",
        help="For et rektangulært rom: (bredde + lengde) × 2. Juster for uregelmessige rom, innvendige/utvendige hjørner osv.",
    )

    gulvareal = round(bredde * lengde, 2)
    veggareal = round(lopemeter * hoyde, 2)

    st.info(f"**Gulvareal:** {gulvareal} m²  |  **Veggareal:** {veggareal} m²")

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 1
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            # Sjekk om arealene har endret seg – i så fall nullstill mengder
            forrige_areal = st.session_state.get("_prev_areal")
            ny_areal = (gulvareal, veggareal)
            if forrige_areal is not None and forrige_areal != ny_areal:
                for item in FLISARBEIDER:
                    if item["kategori"] in ("gulv", "vegg"):
                        nk = f"mengde_{item['id']}"
                        if nk in st.session_state:
                            del st.session_state[nk]

            st.session_state.update(
                bredde=bredde, lengde=lengde, hoyde=hoyde,
                lopemeter=lopemeter, gulvareal=gulvareal,
                veggareal=veggareal, _prev_areal=ny_areal,
            )
            st.session_state.steg = 3
            st.rerun()

# ===================================================================
# STEG 3 – Velg tjeneste
# ===================================================================
elif st.session_state.steg == 3:
    st.subheader("Velg tjeneste")

    tjeneste = st.radio(
        "Hva ønsker du å kalkulere?",
        options=["Flisarbeider", "Tømrerarbeider"],
        index=0 if st.session_state.get("tjeneste", "Flisarbeider") == "Flisarbeider" else 1,
    )

    if tjeneste == "Tømrerarbeider":
        st.warning("Tømrerarbeider er under utvikling og ikke tilgjengelig ennå.")

    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 2
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            if tjeneste == "Tømrerarbeider":
                st.error("Tømrerarbeider er ikke tilgjengelig ennå.")
            else:
                st.session_state.tjeneste = tjeneste
                st.session_state.steg = 4
                st.rerun()

# ===================================================================
# STEG 4 – Flisarbeider detaljer
# ===================================================================
elif st.session_state.steg == 4:
    st.subheader("Flisarbeider – Velg poster")

    gulvareal = st.session_state.get("gulvareal", 0)
    veggareal = st.session_state.get("veggareal", 0)

    st.caption(f"Gulvareal: {gulvareal} m²  |  Veggareal: {veggareal} m²")
    st.divider()

    poster = []

    for item in FLISARBEIDER:
        # Bestem standard-mengde
        if item["kategori"] == "gulv":
            std_mengde = gulvareal
        elif item["kategori"] == "vegg":
            std_mengde = veggareal
        elif item["kategori"] == "fast":
            std_mengde = 1.0
        else:
            std_mengde = float(item.get("std_mengde", 1.0))

        kol1, kol2, kol3 = st.columns([3, 1.2, 1.2])

        with kol1:
            inkludert = st.checkbox(
                f"{item['navn']}  —  {fmt(item['pris'])} kr/{item['enhet']}",
                value=st.session_state.get(f"inkl_{item['id']}", item["standard"]),
                key=f"inkl_{item['id']}",
            )

        mengde = 0.0
        total = 0.0

        if inkludert:
            with kol2:
                if item["kategori"] == "fast":
                    mengde = 1.0
                    st.markdown(f"&nbsp;\n\n`1 {item['enhet']}`")
                elif item["kategori"] == "stk":
                    mengde = float(
                        st.number_input(
                            "Antall",
                            min_value=0, max_value=50,
                            value=int(st.session_state.get(f"mengde_{item['id']}", max(1, int(std_mengde)))),
                            step=1,
                            key=f"mengde_{item['id']}",
                            label_visibility="collapsed",
                        )
                    )
                else:
                    mengde = st.number_input(
                        "Mengde",
                        min_value=0.0, max_value=500.0,
                        value=float(st.session_state.get(f"mengde_{item['id']}", std_mengde)),
                        step=0.1, format="%.2f",
                        key=f"mengde_{item['id']}",
                        label_visibility="collapsed",
                    )

            total = item["pris"] * mengde
            with kol3:
                st.markdown(f"&nbsp;\n\n**{fmt(total)} kr**")

            poster.append({
                "navn": item["navn"],
                "mengde": mengde,
                "enhet": item["enhet"],
                "pris": item["pris"],
                "total": total,
            })

    # --- Epoxyfug ---
    st.divider()
    st.markdown("**Epoxyfug (tillegg)**")
    epoxy_valg = st.selectbox(
        "Velg størrelse",
        options=list(EPOXY_VALG.keys()),
        index=list(EPOXY_VALG.keys()).index(
            st.session_state.get("epoxy_valg", "Ikke inkludert")
        ),
        key="epoxy_valg_widget",
        label_visibility="collapsed",
    )

    epoxy_pris = EPOXY_VALG[epoxy_valg]
    if epoxy_pris > 0:
        st.markdown(f"Epoxyfug tillegg: **{fmt(epoxy_pris)} kr**")

    # --- Forhåndsvisning av totalsum ---
    st.divider()
    forhåndssum = sum(p["total"] for p in poster) + epoxy_pris
    st.markdown(f"### Foreløpig sum eks. mva: {fmt(forhåndssum)} kr")

    # --- Navigasjon ---
    kol_v, kol_h = st.columns(2)
    with kol_v:
        if st.button("← Tilbake", use_container_width=True):
            st.session_state.steg = 3
            st.rerun()
    with kol_h:
        if st.button("Neste →", use_container_width=True, type="primary"):
            if not poster:
                st.error("Du må velge minst én post.")
            else:
                st.session_state.poster = poster
                st.session_state.epoxy_valg = epoxy_valg
                st.session_state.epoxy_pris = epoxy_pris
                st.session_state.steg = 5
                st.rerun()

# ===================================================================
# STEG 5 – Oppsummering og eksport
# ===================================================================
elif st.session_state.steg == 5:
    st.subheader("Oppsummering")

    adresse = st.session_state.get("adresse", "")
    poster = st.session_state.get("poster", [])
    epoxy_pris = st.session_state.get("epoxy_pris", 0)
    epoxy_valg = st.session_state.get("epoxy_valg", "Ikke inkludert")
    gulvareal = st.session_state.get("gulvareal", 0)
    veggareal = st.session_state.get("veggareal", 0)

    st.markdown(f"**Prosjekt:** {adresse}")
    st.markdown(f"**Dato:** {datetime.date.today().strftime('%d.%m.%Y')}")
    st.markdown(f"**Gulvareal:** {gulvareal} m²  |  **Veggareal:** {veggareal} m²")
    st.divider()

    # Tabell
    if poster:
        for post in poster:
            if post["mengde"] > 0:
                kol1, kol2, kol3 = st.columns([3, 1.5, 1.5])
                with kol1:
                    st.markdown(post["navn"])
                with kol2:
                    st.markdown(f"{post['mengde']:.2f} {post['enhet']}  ×  {fmt(post['pris'])} kr")
                with kol3:
                    st.markdown(f"**{fmt(post['total'])} kr**")

    if epoxy_pris > 0:
        kol1, kol2, kol3 = st.columns([3, 1.5, 1.5])
        with kol1:
            st.markdown("Epoxyfug")
        with kol2:
            st.markdown(f"1 stk  ×  {fmt(epoxy_pris)} kr")
        with kol3:
            st.markdown(f"**{fmt(epoxy_pris)} kr**")

    # Totaler
    subtotal = sum(p["total"] for p in poster if p["mengde"] > 0) + epoxy_pris
    mva = subtotal * MVA_SATS
    total_inkl = subtotal + mva

    st.divider()
    kol_tom, kol_t = st.columns([2, 2])
    with kol_t:
        st.markdown(f"**Sum eks. mva:** {fmt(subtotal)} kr")
        st.markdown(f"**MVA 25%:** {fmt(mva)} kr")
        st.markdown(f"### Total inkl. mva: {fmt(total_inkl)} kr")

    # Lagre totaler for eksport
    eksport_data = {
        "adresse": adresse,
        "gulvareal": gulvareal,
        "veggareal": veggareal,
        "tjeneste": st.session_state.get("tjeneste", "Flisarbeider"),
        "poster": poster,
        "epoxy_valg": epoxy_valg,
        "epoxy_pris": epoxy_pris,
        "subtotal": subtotal,
        "mva": mva,
        "total_inkl": total_inkl,
    }

    # --- Eksport ---
    st.divider()
    st.subheader("Eksporter kalkyle")

    filnavn_base = f"kalkyle_{trygt_filnavn(adresse)}_{datetime.date.today()}"

    kol1, kol2 = st.columns(2)
    with kol1:
        pdf_bytes = generer_pdf(eksport_data)
        st.download_button(
            "Last ned PDF",
            data=pdf_bytes,
            file_name=f"{filnavn_base}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with kol2:
        excel_bytes = generer_excel(eksport_data)
        st.download_button(
            "Last ned Excel",
            data=excel_bytes,
            file_name=f"{filnavn_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Navigasjon
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
