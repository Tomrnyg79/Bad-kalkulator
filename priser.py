"""
Priskonfigurasjon for Bad-Kalkulator.
Oppdater prisene og firmainformasjon her.
"""

FIRMA = {
    "navn": "Nygård Bad AS",
    "orgnr": "937 035 969",
    "adresse": "Klebersteinsveien 78C, 3520 Jevnaker",
    "telefon": "46 30 31 87 / 92 34 75 34",
    "epost": "post@nygardbad.no",
}

MVA_SATS = 0.25

# --- Flisarbeider ---
FLIS = {
    "gulvstop": 1350,
    "membran_vegg": 375,
    "membran_gulv": 750,
    "flis_vegg_base": 1000,
    "flis_gulv_base": 1200,
    "flis_dusj": 1500,
    "sokkelflis": 250,
    "cisternekasse": 3750,
    "dokumentasjon": 3500,
    "nisje_flis": 3500,
    "ekstra_sluk": 1000,
    "hjornelist": 1500,
    "gjaring_hjorne": 2000,
    "stor_flis_faktor": 1.30,
}

EPOXY_VALG = {
    "Ikke inkludert": 0,
    "Liten (3 000 kr)": 3000,
    "Medium (4 500 kr)": 4500,
    "Stor (6 000 kr)": 6000,
}

# --- Toemrerarbeid ---
TOMRER = {
    "isolering_standard": 220,
    "isolering_tak": 290,
    "paforing_vegg": 145,
    "finerplater": 150,
    "vatromsplater": 170,
    "nedforing_tak": 180,
    "gips_tak": 180,
    "innerdor": 2640,
    "skyvedor": 3300,
    "nisje": 1900,
    "utvendig_hjorne": 750,
    "ekstra_innvendig_hjorne": 250,
    "timepris": 825,
}
