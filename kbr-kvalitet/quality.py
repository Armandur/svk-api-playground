from collections import defaultdict
from datetime import datetime

from matching import sweref_to_wgs84

LANG_BYGG       = 300
STALE_DATE      = datetime(2020, 1, 1)
STATUS_EJ_AKTIV = {"Kyrkan används inte"}


def run_all_checks(churches_raw: list[dict]) -> dict[str, list]:
    datum_omojligt:   list[dict] = []
    datum_samma_ar:   list[dict] = []
    datum_saknas:     list[dict] = []
    byggnadstid_lang: list[dict] = []
    koord_utanfor:    list[dict] = []
    koord_rundad:     list[dict] = []
    status_ej_aktiv:  list[dict] = []
    funktion_andrad:  list[dict] = []
    raa_saknas:       list[dict] = []
    byggarea_saknas:  list[dict] = []
    fastighet_saknas: list[dict] = []
    planform_saknas:  list[dict] = []
    material_saknas:  list[dict] = []
    tillg_ej_prog:    list[dict] = []
    ej_tillganglig:   list[dict] = []
    andrad_gammal:    list[dict] = []
    agare_mismatch:   list[dict] = []

    coord_groups: dict[tuple, list] = defaultdict(list)
    name_stift:   dict[str,   list] = defaultdict(list)

    for b in churches_raw:
        x, y = b.get("xKoordinat"), b.get("yKoordinat")
        if x is None or y is None:
            continue
        lat, lng = sweref_to_wgs84(x, y)
        bygg, invigd = b.get("nybyggnadFran"), b.get("invigning")
        namn, stift  = b["namn"], b.get("stift", "")
        base = {"kbr_id": b["id"], "namn": namn, "stift": stift,
                "funktion": b.get("nuvarandeFunktion", ""),
                "kbr_lat": lat, "kbr_lng": lng}

        # Datumkvalitet
        if bygg and invigd:
            if bygg > invigd:
                datum_omojligt.append({**base, "nybyggnadFran": bygg,
                                       "invigning": invigd, "diff_år": invigd - bygg})
            elif bygg == invigd:
                datum_samma_ar.append({**base, "år": bygg})
            elif invigd - bygg > LANG_BYGG:
                byggnadstid_lang.append({**base, "nybyggnadFran": bygg,
                                         "invigning": invigd, "byggnadstid": invigd - bygg})
        elif bygg is None and invigd is None:
            datum_saknas.append({**base, "saknas": "båda"})
        elif bygg is None:
            datum_saknas.append({**base, "saknas": "nybyggnadFran", "invigning": invigd})
        else:
            datum_saknas.append({**base, "saknas": "invigning", "nybyggnadFran": bygg})

        # Koordinatkvalitet
        if not (55.0 < lat < 70.5 and 10.0 < lng < 25.0):
            koord_utanfor.append({**base, "kbr_lat": lat, "kbr_lng": lng})
        if int(x) % 1000 == 0 and int(y) % 1000 == 0:
            koord_rundad.append({**base, "kbr_x": int(x), "kbr_y": int(y)})

        # Duplikat-index (byggs här, aggregeras nedan)
        coord_groups[(lat, lng)].append({"kbr_id": b["id"], "namn": namn, "stift": stift})
        name_stift[f"{namn}||{stift}"].append(
            {"kbr_id": b["id"], "stift": stift, "kbr_lat": lat, "kbr_lng": lng})

        # Status
        freq = b.get("anvandningsfrekvens", "")
        if freq in STATUS_EJ_AKTIV:
            status_ej_aktiv.append({**base, "anvandningsfrekvens": freq, "invigning": invigd})

        nuv  = b.get("nuvarandeAnvandning", "")
        ursp = b.get("ursprungligAnvandning", "")
        if nuv and ursp:
            if nuv.lower().startswith("kyrka") != ursp.lower().startswith("kyrka"):
                funktion_andrad.append({**base, "ursprunglig": ursp,
                                        "nuvarande": nuv, "invigning": invigd})

        # Komplettering
        if not b.get("identitetRAA"):
            raa_saknas.append({**base, "invigning": invigd,
                               "skyddEnligtKML": b.get("skyddEnligtKML", "")})
        if not b.get("byggarea"):
            byggarea_saknas.append({**base, "invigning": invigd})
        if not b.get("fastighetsbeteckning"):
            fastighet_saknas.append({**base, "invigning": invigd})
        if not b.get("planform"):
            planform_saknas.append({**base, "invigning": invigd})
        stomme = b.get("materialStomme") or ""
        fasad  = b.get("materialFasad") or ""
        if not stomme or not fasad:
            saknar = "båda" if (not stomme and not fasad) \
                     else ("stomme" if not stomme else "fasad")
            material_saknas.append({**base, "saknar": saknar,
                                    "materialStomme": stomme or "-",
                                    "materialFasad": fasad or "-"})

        # Tillgänglighet
        prog = b.get("handlingsprogramTillganglighet") or ""
        anp  = b.get("tillganglighetsanpassning") or ""
        if not prog or prog == "Handlingsprogram finns inte":
            tillg_ej_prog.append({**base, "program": prog or "(tomt)", "anpassning": anp})
        if anp == "Inte tillgänglighetsanpassad":
            ej_tillganglig.append({**base, "anpassning": anp, "program": prog})

        # Förvaltning
        agare = b.get("agandeEnhet") or ""
        geo   = b.get("geografiskEnhet") or ""
        if agare and geo and agare != geo:
            agare_mismatch.append({**base, "agandeEnhet": agare, "geografiskEnhet": geo})

        andrad_str = b.get("andradDatum") or ""
        if andrad_str:
            try:
                andrad = datetime.fromisoformat(andrad_str)
                if andrad.replace(tzinfo=None) < STALE_DATE:
                    andrad_gammal.append({**base,
                        "andradDatum": andrad_str[:10],
                        "skapadDatum": (b.get("skapadDatum") or "")[:10],
                        "invigning": invigd})
            except ValueError:
                pass

    koord_duplikat = [
        {"kbr_lat": k[0], "kbr_lng": k[1], "kyrkor": v}
        for k, v in coord_groups.items() if len(v) > 1
    ]
    namn_duplikat = [
        {"namn": k.split("||")[0], "stift": k.split("||")[1], "kyrkor": v}
        for k, v in name_stift.items() if len(v) > 1
    ]

    return {
        "datum_omojligt":  datum_omojligt,
        "datum_samma_ar":  datum_samma_ar,
        "datum_saknas":    datum_saknas,
        "byggnadstid_lang": byggnadstid_lang,
        "koord_utanfor":   koord_utanfor,
        "koord_rundad":    koord_rundad,
        "koord_duplikat":  koord_duplikat,
        "namn_duplikat":   namn_duplikat,
        "status_ej_aktiv": status_ej_aktiv,
        "funktion_andrad": funktion_andrad,
        "raa_saknas":      raa_saknas,
        "byggarea_saknas": byggarea_saknas,
        "fastighet_saknas": fastighet_saknas,
        "planform_saknas": planform_saknas,
        "material_saknas": material_saknas,
        "tillg_ej_prog":   tillg_ej_prog,
        "ej_tillganglig":  ej_tillganglig,
        "andrad_gammal":   andrad_gammal,
        "agare_mismatch":  agare_mismatch,
    }
