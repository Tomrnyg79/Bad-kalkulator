"""
Priskonfigurasjon for Bad-Kalkulator.
Oppdater prisene og firmainformasjon her.
"""

# --- Firmainformasjon ---
FIRMA = {
    "navn": "Nygård Bad AS",
    "orgnr": "937 035 969",
    "adresse": "Klebersteinsveien 78C, 3520 Jevnaker",
    "telefon": "46 30 31 87 / 92 34 75 34",
    "epost": "post@nygardbad.no",
}

# MVA-sats
MVA_SATS = 0.25

# --- Priser for flisarbeider ---
FLISARBEIDER = [
    {
        "id": "gulvstop",
        "navn": "Gulvstøp",
        "pris": 1350,
        "enhet": "m²",
        "kategori": "gulv",
        "standard": True,
    },
    {
        "id": "membran_vegg",
        "navn": "Membran vegg",
        "pris": 375,
        "enhet": "m²",
        "kategori": "vegg",
        "standard": True,
    },
    {
        "id": "membran_gulv",
        "navn": "Membran gulv",
        "pris": 750,
        "enhet": "m²",
        "kategori": "gulv",
        "standard": True,
    },
    {
        "id": "flis_vegg",
        "navn": "Flislegging vegg 60x60",
        "pris": 1000,
        "enhet": "m²",
        "kategori": "vegg",
        "standard": True,
    },
    {
        "id": "flis_gulv",
        "navn": "Flislegging gulv",
        "pris": 1200,
        "enhet": "m²",
        "kategori": "gulv",
        "standard": True,
    },
    {
        "id": "flis_dusj",
        "navn": "Flislegging dusjgulv",
        "pris": 1500,
        "enhet": "m²",
        "kategori": "manuell",
        "standard": True,
        "std_mengde": 1.0,
    },
    {
        "id": "cisternekasse",
        "navn": "Cisternekasse med gjæring",
        "pris": 3750,
        "enhet": "stk",
        "kategori": "stk",
        "standard": False,
        "std_mengde": 0,
    },
    {
        "id": "dokumentasjon",
        "navn": "Dokumentasjon",
        "pris": 3500,
        "enhet": "bad",
        "kategori": "fast",
        "standard": True,
    },
    {
        "id": "nisje",
        "navn": "Nisje med gjæring",
        "pris": 3500,
        "enhet": "stk",
        "kategori": "stk",
        "standard": False,
        "std_mengde": 0,
    },
]

# Epoxyfug - variabel pris basert på størrelse
EPOXY_VALG = {
    "Ikke inkludert": 0,
    "Liten (3 000 kr)": 3000,
    "Medium (4 500 kr)": 4500,
    "Stor (6 000 kr)": 6000,
}
