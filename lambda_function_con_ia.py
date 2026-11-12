"""
Prisma BMV - Código Oficial para AWS Lambda con Inferencia de IA (Capa Gold)
Archivo: lambda_function_con_ia.py
Instrucciones: Copia todo este archivo y pégalo en lambda_function.py en la consola de AWS Lambda.
"""

import datetime
import hashlib
import io
import json
import os
import re
import traceback
import urllib.request
from pathlib import Path
try:
    import boto3
except ImportError:
    boto3 = None
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURACIÓN DEL DATA LAKE
# ==============================================================================
# IMPORTANTE: Reemplaza con el nombre exacto de tu bucket en Amazon S3:
BUCKET_NAME = "prisma-bmv-datalake-tunombre-2026"

EMISORAS_15 = [
    ("GMEXICO", "B", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Mineria y materiales"),
    ("GFNORTE", "O", "Anillo 2 (Plata: Seleccion Modelo Sectorial)", "Banca y servicios financieros"),
    ("FEMSA", "UBD", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Consumo y comercio"),
    ("AMX", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Telecomunicaciones"),
    ("WALMEX", "*", "Anillo 1 (Oro: Inferencia Prospectiva Estricta)", "Comercio y autoservicio"),
    ("CEMEX", "CPO", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Cemento y construccion"),
    ("PE&OLES", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Mineria y metales"),
    ("GAP", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("AC", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Bebidas y consumo"),
    ("ASUR", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Infraestructura aeroportuaria"),
    ("BIMBO", "A", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
    ("GFINBUR", "O", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Servicios financieros"),
    ("VESTA", "*", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Inmuebles industriales"),
    ("LIVEPOL", "C-1", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Comercio departamental"),
    ("GRUMA", "B", "Anillo 3 (Bronce: Ingesta Big Data en Vivo)", "Industria alimentaria"),
]

# Parámetros matemáticos oficiales calibrados de los modelos de 2ª Generación (Panel G2)
FECHA_CONGELAMIENTO_G2 = "2026-11-06"

MODELOS_G2_CONFIG = {
    "G2_V1_POOLED_REL3_CALIBRADO": {
        "beta": [
            0.005433415366661381,
            -0.1539955487246032,
            -0.025368265491349146,
            -0.01688957679188532,
        ],
        "c_val": 0.01,
        "tau_val": 0.0,
        "scalers": {
            "AC": {
                "mean": [0.030124455576127963, 0.021325641636384694, 0.016857566120422638],
                "scale": [0.04012680236739293, 0.026890677325181928, 0.002230749459648026],
            },
            "AMX": {
                "mean": [0.002394785126200835, -0.0004651210871758049, 0.014316856483589123],
                "scale": [0.04485867200778437, 0.033982109283084996, 0.0039810069648410495],
            },
            "CEMEX": {
                "mean": [-0.005742791688955511, -0.003629224029781822, 0.020346851195101434],
                "scale": [0.05963533309471803, 0.04344965071817206, 0.00594087811029654],
            },
            "FEMSA": {
                "mean": [0.004712436181594009, -0.0011434079539107246, 0.014098318047991401],
                "scale": [0.041797100787601106, 0.03286634212032672, 0.005690603383349724],
            },
            "GAP": {
                "mean": [-0.010012494689079764, -0.007284349623677642, 0.01748305049312403],
                "scale": [0.04539372418925715, 0.03320995299607904, 0.002695859465140558],
            },
            "GFNORTE": {
                "mean": [0.005374648387568126, 0.002735221953207007, 0.019950070668235863],
                "scale": [0.0601247723400722, 0.040525180642345573, 0.007539419332104307],
            },
            "GMEXICO": {
                "mean": [0.0043786776830264, -0.0003373370957790848, 0.021704962257778994],
                "scale": [0.06745282450133415, 0.047268359407333156, 0.006695997641557037],
            },
            "WALMEX": {
                "mean": [0.002676492453048578, -0.00016248491396972587, 0.015632228500274944],
                "scale": [0.04093897756979405, 0.03522844927361116, 0.004317623475741711],
            },
        },
    },
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL": {
        "beta": [
            -0.0005372298629247181,
            -0.14633801368097235,
            -0.03715318214448395,
            -0.01713404973384365,
        ],
        "c_val": 0.01,
        "tau_val": 0.0025,
        "scalers": {
            "AC": {
                "mean": [0.02912898944483185, 0.02068639617838575, 0.016780503043804323],
                "scale": [0.04052220570011292, 0.027174409858313157, 0.002234785080461849],
            },
            "AMX": {
                "mean": [0.0020879500690047276, -0.0004012473656601024, 0.014358529153663398],
                "scale": [0.04484771621874373, 0.03384239606561156, 0.003979776025437052],
            },
            "CEMEX": {
                "mean": [-0.006314574048483072, -0.0037769019592714223, 0.02034966345302264],
                "scale": [0.05857620903404476, 0.04311308423161766, 0.005967568766338803],
            },
            "FEMSA": {
                "mean": [0.003937726856127934, -0.0013552076436825604, 0.014148081754337394],
                "scale": [0.042559207394950414, 0.032968251997085196, 0.00571372818872318],
            },
            "GAP": {
                "mean": [-0.00806919518246504, -0.008438937135605935, 0.017455453204940543],
                "scale": [0.0464214726051533, 0.03413242071280712, 0.00279492624142472],
            },
            "GFNORTE": {
                "mean": [0.005101518446326817, 0.002335978687696779, 0.020063052334437254],
                "scale": [0.060851181952885865, 0.04087426740791235, 0.00761263792593381],
            },
            "GMEXICO": {
                "mean": [0.0043507724319138685, -0.0003342437056139102, 0.021786844297684578],
                "scale": [0.06775155750406937, 0.04746939358789894, 0.006698269061195683],
            },
            "WALMEX": {
                "mean": [0.0026755861173208793, -0.0003167914227041298, 0.015650842228561827],
                "scale": [0.041260081217605785, 0.03544254691117036, 0.004284155585618984],
            },
        },
    },
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO": {
        "beta": [
            0.009712203950823273,
            -0.08495976524845908,
            -0.03280077586865846,
            -9.77961875254764e-05,
        ],
        "c_val": 0.001,
        "tau_val": 0.0,
        "scalers": {
            "AC": {
                "mean": [0.025642788868748764, 0.01938235129735557, 0.016266034934776182],
                "scale": [0.04095779122799689, 0.02678048873470154, 0.0027884457382042894],
            },
            "AMX": {
                "mean": [0.002283508847346695, -0.001543291439249721, 0.014154719539244843],
                "scale": [0.04467211800271324, 0.03486490171765837, 0.003935666338039027],
            },
            "CEMEX": {
                "mean": [-0.0003311944598099315, -0.0015687317392691093, 0.019857934096466266],
                "scale": [0.05906081851126594, 0.0448912409520627, 0.0056418615829409765],
            },
            "FEMSA": {
                "mean": [0.0033161076136443944, -0.002219495799909241, 0.01421813426106042],
                "scale": [0.04245621891796628, 0.03460534481404334, 0.005536438238890149],
            },
            "GAP": {
                "mean": [-0.008875628807395449, -0.012289990145881937, 0.019569236756102712],
                "scale": [0.058147495637394554, 0.052491774484828134, 0.0039942608107107445],
            },
            "GFNORTE": {
                "mean": [0.005983163923856323, 0.0023447771879313893, 0.0193549631937393],
                "scale": [0.05800225438105065, 0.03968712461269719, 0.007242924458079659],
            },
            "GMEXICO": {
                "mean": [0.009295465427211477, 0.0036023579431640257, 0.021407927149492228],
                "scale": [0.06527097781600143, 0.04710561878630271, 0.006342754737682209],
            },
            "PE&OLES": {
                "mean": [0.10393017750438382, 0.06566464456128583, 0.03899574308162911],
                "scale": [0.13174920707487042, 0.10350782308779158, 0.005333636362820563],
            },
            "WALMEX": {
                "mean": [0.0011904023528049221, -0.002706195537391022, 0.01559577927711786],
                "scale": [0.040577113588842036, 0.03520829119454824, 0.004334019626540686],
            },
        },
    },
    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO": {
        "beta": [
            0.00974552581342144,
            0.006773459981516012,
            -0.14008618285218138,
            0.0036707954352037963,
            -0.001924898339276406,
        ],
        "c_val": 0.01,
        "tau_val": 0.0,
        "scalers": {
            "AC": {
                "mean": [0.0012096300740078855, 0.0021692575666298615, 0.0016135617762146784, 0.01626603493477618],
                "scale": [0.015113768102684373, 0.01705499111551722, 0.01444554400366296, 0.00278844573820429],
            },
            "AMX": {
                "mean": [-0.00015980769988492528, 0.0001086709441533519, -0.00025982571717859596, 0.014154719539244857],
                "scale": [0.011700528529231126, 0.01591539637048299, 0.01275702179847685, 0.003935666338039031],
            },
            "CEMEX": {
                "mean": [-0.00030310225678744637, 4.750872293695078e-05, -0.00022883182997204016, 0.019857934096466273],
                "scale": [0.015275971593414327, 0.0224829877753107, 0.016392951769408772, 0.005641861582940977],
            },
            "FEMSA": {
                "mean": [-0.00042547446594063196, 0.00036879299478222513, -0.0005774450819882144, 0.014218134261060425],
                "scale": [0.011552178823235304, 0.01379555626328459, 0.01217419030970858, 0.005536438238890149],
            },
            "GAP": {
                "mean": [-0.0027965678960595966, -0.0033860953697622013, -0.003666725760032096, 0.019569236756102715],
                "scale": [0.0155065321118204, 0.021822271758616795, 0.01777140096206519, 0.0039942608107107445],
            },
            "GFNORTE": {
                "mean": [0.0002684040671284528, 0.0007684101134667636, 0.0004412373617686777, 0.0193549631937393],
                "scale": [0.014641813671407957, 0.021746316825823387, 0.015302328058853426, 0.007242924458079654],
            },
            "GMEXICO": {
                "mean": [0.00046721247547774176, 0.0016529325360134528, 0.00073543195455221, 0.021407927149492193],
                "scale": [0.016509957828454894, 0.024228665181904772, 0.01789691819894453, 0.006342754737682215],
            },
            "PE&OLES": {
                "mean": [0.005988121634550277, 0.015426572653618159, 0.009524704260681848, 0.038995743081629106],
                "scale": [0.02790767864064631, 0.04477431272260242, 0.03358741000998932, 0.005333636362820564],
            },
            "WALMEX": {
                "mean": [-0.00021392012084793947, -1.1325963873881263e-06, -0.0004406255126985575, 0.01559577927711786],
                "scale": [0.013082041826608966, 0.016053171971051702, 0.013447482528391383, 0.004334019626540685],
            },
        },
    },
    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL": {
        "c_val": 0.01,
        "tau_val": 0.0,
        "amx_momentum_beta": [
            -0.04258971294560186,
            0.2006510384352254,
            0.12249319457070595,
            -0.2842180577955121,
            -0.022877413816523254,
            0.03839060451586779,
            0.21639368351983246,
        ],
        "amx_momentum_mean": [
            0.0008854122233151779,
            0.005296559877299279,
            0.0001086709441533519,
            0.0014986702193575691,
            -0.001543291439249721,
            0.014154719539244857,
        ],
        "amx_momentum_scale": [
            0.03203302368977134,
            0.061530641177062965,
            0.01591539637048299,
            0.03461154596889674,
            0.03486490171765836,
            0.003935666338039031,
        ],
    },
    "G2_V4_F1_GAP": {
        "beta": [
            0.0413563667139676,
            0.0060643952437239275,
            -0.14653885709458717,
            0.015391394854460382,
            -0.0026388050706440402,
            0.05933854271442315,
        ],
        "c_val": 0.01,
        "tau_val": 0.0,
        "scalers": {
            "AC": {
                "mean": [0.0016257962367741726, 0.002606843066617699, 0.0018743065490128162, 0.016258021752971613, 0.00041263851348034516],
                "scale": [0.014964043725497866, 0.016604563639196542, 0.014035047484988173, 0.002804902963240337, 0.0026482981834702363],
            },
            "AMX": {
                "mean": [-0.0002151378158292618, 0.0002798828833775472, -0.00036303844574388596, 0.014177509769681464, -0.00021942604761184477],
                "scale": [0.011658943591424487, 0.015889023055053526, 0.012731435742514622, 0.003942211943178491, 0.001903450305387523],
            },
            "CEMEX": {
                "mean": [-0.00037030606821068275, 0.00015955184716942385, -0.00036892890672573104, 0.019776609935519246, -0.00014395519785069153],
                "scale": [0.015211778393460997, 0.02240243983329347, 0.01627559076093243, 0.005705917279048344, 0.00216876059576088],
            },
            "FEMSA": {
                "mean": [-0.00046537384636356066, 0.0005987856913763974, -0.0006481732174067022, 0.014298973769852525, -8.178313985472368e-05],
                "scale": [0.011557017326811593, 0.013846762549555476, 0.012251602349410645, 0.005569219947079057, 0.0018437677812956762],
            },
            "GAP": {
                "mean": [-0.0026533611719660745, -0.0029496162099891814, -0.003569898981660968, 0.019538048465428018, 0.0007616943319442362],
                "scale": [0.015194725916049815, 0.021843817145954944, 0.017666135931276056, 0.003953473868416013, 0.0027000467320890667],
            },
            "GFNORTE": {
                "mean": [0.00036060068515266863, 0.0012130548590698167, 0.0006023274846316615, 0.019306499586154324, 3.0307437827939288e-05],
                "scale": [0.014564395503214275, 0.0216790739703789, 0.01526451328990345, 0.007198188999501691, 0.002469652879813279],
            },
            "GMEXICO": {
                "mean": [0.00048711463380427406, 0.00203448876634674, 0.0007943188854119841, 0.02138838508499394, -0.0001358912838260009],
                "scale": [0.016526799491906947, 0.02427475319478139, 0.017974445313915777, 0.00632506324968901, 0.0026003265227645287],
            },
            "PE&OLES": {
                "mean": [0.006066025260259494, 0.015680416929914513, 0.009648387428649466, 0.03900943883981546, -0.001884596508626328],
                "scale": [0.028015469631096353, 0.044666724983223514, 0.03350907434306553, 0.005328795253425963, 0.003981049015158077],
            },
            "WALMEX": {
                "mean": [-0.00022212201654712784, 0.0002656305926857591, -0.00044992107394327294, 0.015498884549983227, 0.00011846455189528602],
                "scale": [0.013082660377329622, 0.016004470455884063, 0.013464740519700867, 0.00436954169493958, 0.00230446885305892],
            },
        },
    },
}


def _normalizar_entrada_registro(raw_dict: dict) -> dict:
    """
    Normaliza un diccionario de registro de modelos (ya sea `registro_modelos_g2_v2.json`
    o `registro_modelos_g2_oficial.json`) al esquema interno consumido por `inferir_modelos_g2`.
    """
    out = {}
    fuente_oficial = raw_dict.get("modelos_congelados_oficiales", raw_dict)
    for mod_id, cfg in fuente_oficial.items():
        if not isinstance(cfg, dict):
            continue
        item = dict(cfg)
        if "scalers_por_emisora" in item and "scalers" not in item:
            item["scalers"] = item["scalers_por_emisora"]
        if "amx_momentum_local" in item:
            amx_loc = item["amx_momentum_local"]
            item["amx_momentum_beta"] = amx_loc.get("beta", [])
            item["amx_momentum_mean"] = amx_loc.get("mean", [])
            item["amx_momentum_scale"] = amx_loc.get("scale", [])
        out[mod_id] = item

    modelos_f1_f3 = raw_dict.get("modelos_fase1_fase3", {})
    for mod_id, cfg in modelos_f1_f3.items():
        if not isinstance(cfg, dict):
            continue
        item = dict(cfg)
        if "scalers_por_emisora" in item and "scalers" not in item:
            item["scalers"] = item["scalers_por_emisora"]
        out[mod_id] = item
    return out


def cargar_registro_modelos_g2(
    s3_client=None,
    bucket_name: str = BUCKET_NAME,
    local_path: str | Path | None = None,
) -> dict:
    """
    Carga dinámicamente el registro de modelos en doble precisión desde:
    1. `local_path` explícito (si se proporciona),
    2. `registro_modelos_g2_v2.json` o `registro_modelos_g2_oficial.json` en disco local,
    3. S3 (`modelos/registro_modelos_g2_v2.json` o `modelos/registro_modelos_g2_oficial.json`),
    4. Fallback determinista en memoria `MODELOS_G2_CONFIG` (doble precisión).
    """
    candidatos_locales = []
    if local_path is not None:
        candidatos_locales.append(Path(local_path))
    base_dir = Path(__file__).resolve().parent
    candidatos_locales.extend(
        [
            base_dir / "registro_modelos_g2_v2.json",
            base_dir / "registro_modelos_g2_oficial.json",
        ]
    )
    for p in candidatos_locales:
        try:
            if p.exists():
                raw = json.loads(p.read_text(encoding="utf-8"))
                norm = _normalizar_entrada_registro(raw)
                if "G2_V4_POOLED_DM5_REL_CORTO_PLAZO" in norm:
                    return norm
        except Exception:
            pass

    if s3_client is not None:
        for s3_key in (
            "modelos/registro_modelos_g2_v2.json",
            "modelos/registro_modelos_g2_oficial.json",
        ):
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                raw = json.loads(obj["Body"].read().decode("utf-8"))
                norm = _normalizar_entrada_registro(raw)
                if "G2_V4_POOLED_DM5_REL_CORTO_PLAZO" in norm:
                    return norm
            except Exception:
                pass

    return MODELOS_G2_CONFIG


def calcular_gap_uh_ppp(
    ultimo_mxn: float | None,
    ppp_mxn: float | None,
) -> float | None:
    """
    Calcula la variable intradiaria de microestructura campeona en Fase 3:
        gap_uh_ppp = (ultimo_bmv_mxn - ppp_bmv_mxn) / ppp_bmv_mxn
    Sin imputar si falta cualquiera de los dos precios.
    """
    if ultimo_mxn is None or ppp_mxn is None:
        return None
    try:
        u = float(ultimo_mxn)
        p = float(ppp_mxn)
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(u) and np.isfinite(p) and p > 0.0):
        return None
    return float((u - p) / p)


def descargar_fix_banxico_lambda(fecha_iso: str) -> dict:
    """
    Consulta el tipo de cambio FIX USD/MXN (`SF43718`) en el SIE de Banxico
    para `fecha_iso` usando `os.environ.get('BANXICO_TOKEN')`.
    Jamás expone ni imprime el token en logs.
    """
    token = os.environ.get("BANXICO_TOKEN", "").strip()
    if not token:
        return {
            "fecha": fecha_iso,
            "serie": "SF43718",
            "fix_usd_mxn": None,
            "estado": "SIN_TOKEN_BANXICO_EN_ENTORNO",
        }
    url = (
        f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43718/"
        f"datos/{fecha_iso}/{fecha_iso}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Bmx-Token": token,
            "User-Agent": "PrismaBMV-CloudML/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        series = payload.get("bmx", {}).get("series", [])
        datos = series[0].get("datos", []) if series else []
        if datos:
            dato_str = str(datos[-1].get("dato", "")).replace(",", "").strip()
            if dato_str and dato_str != "N/E":
                return {
                    "fecha": fecha_iso,
                    "serie": "SF43718",
                    "fix_usd_mxn": float(dato_str),
                    "estado": "OK_BANXICO_SIE",
                }
        return {
            "fecha": fecha_iso,
            "serie": "SF43718",
            "fix_usd_mxn": None,
            "estado": "SIN_PUBLICACION_EN_FECHA",
        }
    except Exception:
        return {
            "fecha": fecha_iso,
            "serie": "SF43718",
            "fix_usd_mxn": None,
            "estado": "ERROR_CONEXION_BANXICO",
        }

YF_TICKER_MAP = {
    ("GMEXICO", "B"): "GMEXICOB.MX",
    ("GFNORTE", "O"): "GFNORTEO.MX",
    ("FEMSA", "UBD"): "FEMSAUBD.MX",
    ("AMX", "B"): "AMXB.MX",
    ("WALMEX", "*"): "WALMEX.MX",
    ("CEMEX", "CPO"): "CEMEXCPO.MX",
    ("PE&OLES", "*"): "PENOLES.MX",
    ("GAP", "B"): "GAPB.MX",
    ("AC", "*"): "AC.MX",
    ("ASUR", "B"): "ASURB.MX",
    ("BIMBO", "A"): "BIMBOA.MX",
    ("GFINBUR", "O"): "GFINBURO.MX",
    ("VESTA", "*"): "VESTA.MX",
    ("LIVEPOL", "C-1"): "LIVEPOLC-1.MX",
    ("GRUMA", "B"): "GRUMAB.MX",
}


def fetch_secondary_contingency_quotes(fecha_iso: str) -> tuple[dict, bytes, str, str]:
    """
    Fuente secundaria de contingencia cuando el boletín RSS de la BMV devuelve HTTP 404.
    Calcula el VWAP de los últimos 20 minutos de operación (13:40-14:00 CDMX) o cierre diario
    vía Yahoo Finance Chart API v8 usando únicamente librerías estándar de Python.
    """
    target_dt = datetime.date.fromisoformat(fecha_iso)
    cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
    p1 = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=cdmx_tz).timestamp()) - 86400 * 7
    p2 = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 23, 59, 59, tzinfo=cdmx_tz).timestamp()) + 86400

    quotes = {}
    headers = {"User-Agent": "Mozilla/5.0 PrismaBMV-CloudML/1.0"}

    for ticker, serie, _, _ in EMISORAS_15:
        yf_sym = YF_TICKER_MAP.get((ticker, serie))
        if not yf_sym:
            continue

        url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?period1={p1}&period2={p2}&interval=1d"
        close_day = None
        prev_close = None
        try:
            req_1d = urllib.request.Request(url_1d, headers=headers)
            with urllib.request.urlopen(req_1d, timeout=15) as resp:
                data_1d = json.loads(resp.read().decode("utf-8", errors="ignore"))
            res_1d = data_1d.get("chart", {}).get("result", [])
            if res_1d:
                ts_list = res_1d[0].get("timestamp", []) or []
                closes = res_1d[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) or []
                daily_pairs = []
                for ts, cl in zip(ts_list, closes):
                    if cl is not None:
                        d_str = datetime.datetime.fromtimestamp(ts, tz=cdmx_tz).strftime("%Y-%m-%d")
                        daily_pairs.append((d_str, float(cl)))
                for idx_d, (d_str, cl_val) in enumerate(daily_pairs):
                    if d_str == fecha_iso:
                        close_day = round(cl_val, 2)
                        if idx_d > 0:
                            prev_close = round(daily_pairs[idx_d - 1][1], 2)
                        break
        except Exception:
            pass

        if close_day is None:
            continue

        vwap_ppp = close_day
        p1_1m = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 7, 0, 0, tzinfo=cdmx_tz).timestamp())
        p2_1m = int(datetime.datetime(target_dt.year, target_dt.month, target_dt.day, 16, 0, 0, tzinfo=cdmx_tz).timestamp())
        url_1m = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?period1={p1_1m}&period2={p2_1m}&interval=1m"
        try:
            req_1m = urllib.request.Request(url_1m, headers=headers)
            with urllib.request.urlopen(req_1m, timeout=15) as resp:
                data_1m = json.loads(resp.read().decode("utf-8", errors="ignore"))
            res_1m = data_1m.get("chart", {}).get("result", [])
            if res_1m:
                ts_1m = res_1m[0].get("timestamp", []) or []
                q_1m = res_1m[0].get("indicators", {}).get("quote", [{}])[0]
                c_1m = q_1m.get("close", []) or []
                h_1m = q_1m.get("high", []) or []
                l_1m = q_1m.get("low", []) or []
                v_1m = q_1m.get("volume", []) or []
                pv_sum = 0.0
                v_sum = 0.0
                fallback_prices = []
                for ts, c_v, h_v, l_v, vol_v in zip(ts_1m, c_1m, h_1m, l_1m, v_1m):
                    if c_v is None:
                        continue
                    dt_bar = datetime.datetime.fromtimestamp(ts, tz=cdmx_tz)
                    if dt_bar.strftime("%Y-%m-%d") != fecha_iso:
                        continue
                    hm = dt_bar.hour * 60 + dt_bar.minute
                    if 13 * 60 + 40 <= hm <= 14 * 60:
                        typ_p = (float(h_v) + float(l_v) + float(c_v)) / 3.0 if (h_v is not None and l_v is not None) else float(c_v)
                        vol_bar = float(vol_v) if (vol_v is not None and vol_v > 0) else 0.0
                        pv_sum += typ_p * vol_bar
                        v_sum += vol_bar
                        fallback_prices.append(float(c_v))
                if v_sum > 0:
                    vwap_ppp = round(pv_sum / v_sum, 2)
                elif fallback_prices:
                    vwap_ppp = round(sum(fallback_prices) / len(fallback_prices), 2)
        except Exception:
            pass

        ant = prev_close if (prev_close is not None and prev_close > 0) else close_day
        var_pct = round((vwap_ppp / ant - 1.0) * 100.0, 2) if ant > 0 else 0.0
        quotes[(ticker, serie)] = {
            "ultimo": close_day,
            "anterior": ant,
            "ppp": vwap_ppp,
            "variacion_ppp_vs_anterior_pct": var_pct,
        }

    payload = {
        "fecha": fecha_iso,
        "fuente": "CONTINGENCIA_FUENTE_SECUNDARIA_YAHOO_FINANCE_VWAP_1340_1400",
        "quotes": {f"{k[0]}|{k[1]}": v for k, v in sorted(quotes.items())},
    }
    raw_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    url_contingencia = f"https://query1.finance.yahoo.com/v8/finance/chart/WALMEX.MX?date={fecha_iso}#contingencia_bmv_404"
    return quotes, raw_bytes, sha256_hex, url_contingencia


def parse_bulletin_quotes(raw_html_bytes: bytes) -> dict:
    if not raw_html_bytes:
        return {}
    html_txt = raw_html_bytes.decode("utf-8", errors="ignore")
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html_txt, flags=re.DOTALL | re.IGNORECASE)
    quotes = {}
    for tbl in tables:
        header_text = re.sub(r"<[^>]+>", " ", tbl[:300])
        is_quote_table = (
            ("Negociadas" in header_text or "Variac" in header_text or "Alza" in header_text or "Baja" in header_text)
            and "Paquetes" not in header_text
        )
        if not is_quote_table:
            continue
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.DOTALL | re.IGNORECASE)
        for r in rows:
            tds = re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.DOTALL | re.IGNORECASE)
            clean = [re.sub(r"<[^>]+>", "", td).strip() for td in tds]
            clean = [re.sub(r"\s+", " ", td) for td in clean if td]
            if len(clean) >= 5 and clean[0] not in [
                "Emisora",
                "M&aacute;s Negociadas",
                "Mayor Variaci&oacute;n a la Alza",
                "Mayor Variaci&oacute;n a la Baja",
            ]:
                try:
                    tk = clean[0]
                    sr = clean[1]
                    ult = float(clean[2].replace(",", ""))
                    ant = float(clean[3].replace(",", ""))
                    candidate_ppp = float(clean[4].replace(",", ""))
                    if candidate_ppp <= 0:
                        continue
                    var_pct = round((candidate_ppp / ant - 1.0) * 100.0, 2) if ant > 0 else 0.0
                    k = (tk, sr)
                    if k not in quotes:
                        quotes[k] = {
                            "ultimo": ult,
                            "anterior": ant,
                            "ppp": candidate_ppp,
                            "variacion_ppp_vs_anterior_pct": var_pct,
                        }
                except (ValueError, ZeroDivisionError):
                    pass
    return quotes


# Calendario oficial de días inhábiles BMV.
# 2026: idéntico a `metodologia_ppp.FERIADOS_BMV_2026` (paridad verificada por test).
# Fuente: https://www.bmv.com.mx/es/grupo-bmv/calendario-de-dias-festivos
FERIADOS_BMV_2026 = frozenset({
    "2026-01-01", "2026-02-02", "2026-03-16", "2026-04-02", "2026-04-03",
    "2026-05-01", "2026-09-16", "2026-11-02", "2026-11-16", "2026-12-12", "2026-12-25",
})
# 2027: PROVISIONAL (derivado de la Ley Federal del Trabajo y Semana Santa 2027).
# Debe confirmarse contra el calendario oficial BMV cuando sea publicado.
FERIADOS_BMV_2027_PROVISIONAL = frozenset({
    "2027-01-01", "2027-02-01", "2027-03-15", "2027-03-25", "2027-03-26",
    "2027-09-16", "2027-11-02", "2027-11-15",
})
FERIADOS_BMV = FERIADOS_BMV_2026 | FERIADOS_BMV_2027_PROVISIONAL


def es_sesion_bmv(fecha_iso: str) -> bool:
    """True si `fecha_iso` es día hábil BMV (lunes-viernes y no feriado oficial)."""
    d = datetime.date.fromisoformat(str(fecha_iso)[:10])
    return d.weekday() < 5 and d.isoformat() not in FERIADOS_BMV


def calcular_fecha_h5(fecha_iso: str, n_sesiones: int = 5) -> str:
    """
    Calcula la fecha objetivo a `n_sesiones` sesiones BMV, omitiendo fines de semana
    y feriados oficiales (paridad con `metodologia_ppp.add_bmv_sessions`).
    """
    dt = datetime.date.fromisoformat(fecha_iso)
    agregadas = 0
    while agregadas < n_sesiones:
        dt += datetime.timedelta(days=1)
        if es_sesion_bmv(dt.isoformat()):
            agregadas += 1
    return dt.isoformat()


MAX_SESIONES_RECONCILIACION_CONTINGENCIA = 10

MAPA_SERIE_EMISORA = {tk: sr for tk, sr, _, _ in EMISORAS_15}
MAPA_SECTOR_EMISORA = {tk: sec for tk, _, _, sec in EMISORAS_15}

META_ENTRENAMIENTO_G2 = {
    "G2_V1_POOLED_REL3_CALIBRADO": {
        "modo_entrenamiento": "TRAIN_CONGELADO",
        "n_train_panel": 8122,
        "fin_etiquetas_train_panel": "2025-04-11",
    },
    "G2_V2_POOLED_REL3_ZONA_NEUTRAL": {
        "modo_entrenamiento": "TRAIN_CONGELADO",
        "n_train_panel": 8122,
        "fin_etiquetas_train_panel": "2025-04-11",
    },
    "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO": {
        "modo_entrenamiento": "HISTORIA_PURGADA_HASTA_CORTE",
        "n_train_panel": 9679,
        "fin_etiquetas_train_panel": "2026-10-28",
    },
    "G2_V4_POOLED_DM5_REL_CORTO_PLAZO": {
        "modo_entrenamiento": "HISTORIA_PURGADA_HASTA_CORTE",
        "n_train_panel": 9679,
        "fin_etiquetas_train_panel": "2026-10-28",
    },
    "G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL": {
        "modo_entrenamiento": "HISTORIA_PURGADA_HASTA_CORTE",
        "n_train_panel": 9679,
        "fin_etiquetas_train_panel": "2026-10-28",
    },
    "G2_V4_F1_GAP": {
        "modo_entrenamiento": "HISTORIA_PURGADA_HASTA_CORTE",
        "n_train_panel": 9679,
        "fin_etiquetas_train_panel": "2026-10-28",
    },
}


def contar_sesiones_bmv_entre(fecha_ini_iso: str, fecha_fin_iso: str) -> int:
    """Cuenta cuántas sesiones hábiles BMV hay en el intervalo semiabierto (fecha_ini_iso, fecha_fin_iso]."""
    d_ini = datetime.date.fromisoformat(str(fecha_ini_iso)[:10])
    d_fin = datetime.date.fromisoformat(str(fecha_fin_iso)[:10])
    if d_fin <= d_ini:
        return 0
    cnt = 0
    curr = d_ini
    while curr < d_fin:
        curr += datetime.timedelta(days=1)
        if es_sesion_bmv(curr.isoformat()):
            cnt += 1
    return cnt


def cargar_eventos_corporativos_s3_o_local(
    s3_client=None,
    bucket_name: str = BUCKET_NAME,
    local_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Carga el catálogo de eventos corporativos (dividendos y splits) desde disco local
    (`eventos_corporativos_15_emisoras.csv`) o S3 (`referencia/eventos_corporativos_15_emisoras.csv`).
    """
    candidatos = []
    if local_path is not None:
        candidatos.append(Path(local_path))
    candidatos.append(Path(__file__).resolve().parent / "eventos_corporativos_15_emisoras.csv")
    for p in candidatos:
        try:
            if p.exists():
                return pd.read_csv(p)
        except Exception:
            pass
    if s3_client is not None:
        for s3_key in (
            "referencia/eventos_corporativos_15_emisoras.csv",
            "modelos/eventos_corporativos_15_emisoras.csv",
        ):
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                return pd.read_csv(io.BytesIO(obj["Body"].read()))
            except Exception:
                pass
    return pd.DataFrame(columns=["emisora", "fecha_ex", "tipo", "monto_mxn", "factor", "fuente"])


def calcular_ppp_t5_ajustado_dividendo(
    emisora: str,
    fecha_t_iso: str,
    fecha_h5_iso: str,
    ppp_t5: float,
    df_eventos: pd.DataFrame | None = None,
) -> float:
    """
    Ajusta causalmente `ppp_t5` por cualquier dividendo o split ex-date ocurrido en
    (fecha_t_iso, fecha_h5_iso], replicando la higiene de etiquetas de Fase 1:
        PPP_{t+5, adj} = PPP_{t+5} / prod(factor_{(t, t+5]})
    Si `factor` no está disponible pero sí `monto_mxn`, suma `monto_mxn`.
    """
    if df_eventos is None or df_eventos.empty or not np.isfinite(ppp_t5):
        return float(ppp_t5)
    sub = df_eventos[
        (df_eventos["emisora"].astype(str) == str(emisora))
        & (df_eventos["fecha_ex"].astype(str) > str(fecha_t_iso)[:10])
        & (df_eventos["fecha_ex"].astype(str) <= str(fecha_h5_iso)[:10])
    ]
    if sub.empty:
        return float(ppp_t5)
    f_prod = 1.0
    monto_extra = 0.0
    for _, r in sub.iterrows():
        fac = pd.to_numeric(r.get("factor"), errors="coerce")
        if pd.notna(fac) and float(fac) > 1e-8:
            f_prod *= float(fac)
        else:
            m = pd.to_numeric(r.get("monto_mxn"), errors="coerce")
            if pd.notna(m) and float(m) > 0.0:
                monto_extra += float(m)
    return float(ppp_t5 / max(f_prod, 1e-8) + monto_extra)


def calcular_monitoreo_secuencial_gold(df_gold: pd.DataFrame) -> dict:
    """
    Calcula el monitoreo secuencial activo (CUSUM de Page + SPRT de Wald) sobre las
    señales con `estado_resolucion == 'RESUELTA_OFICIAL_T5'` en la bitácora Gold (P7).
    """
    p0, p1, alpha, beta = 0.50, 0.55, 0.05, 0.20
    frontera_a = float(np.log((1.0 - beta) / alpha))
    frontera_b = float(np.log(beta / (1.0 - alpha)))
    step_hit = float(np.log(p1 / p0))
    step_miss = float(np.log((1.0 - p1) / (1.0 - p0)))
    k_holgura = 0.001
    h_alarma = 1.5

    if df_gold is None or df_gold.empty or "estado_resolucion" not in df_gold.columns:
        return {}

    res_df = df_gold[df_gold["estado_resolucion"] == "RESUELTA_OFICIAL_T5"].copy()
    if res_df.empty or "modelo_g2" not in res_df.columns:
        return {}

    out = {}
    for mod_id, grp in res_df.groupby("modelo_g2"):
        grp_s = grp.sort_values(["fecha_senal", "emisora"])
        probs = pd.to_numeric(grp_s["probabilidad_subida"], errors="coerce").to_numpy(dtype=float)
        ys = pd.to_numeric(grp_s["target_y_observado"], errors="coerce").to_numpy(dtype=float)
        clases = pd.to_numeric(grp_s["prediccion_clase"], errors="coerce").to_numpy(dtype=float)
        mask = np.isfinite(probs) & np.isfinite(ys) & np.isfinite(clases)
        probs, ys, clases = probs[mask], ys[mask], clases[mask]
        n_nom = int(len(ys))
        if n_nom == 0:
            continue
        hits = int(np.sum(clases == ys))
        misses = n_nom - hits
        llr_nom = float(hits * step_hit + misses * step_miss)
        if llr_nom >= frontera_a:
            est_sprt = "ACEPTAR_H1_VENTAJA_DEMOSTRADA"
        elif llr_nom <= frontera_b:
            est_sprt = "ACEPTAR_H0_SIN_VENTAJA"
        else:
            est_sprt = "CONTINUAR_MUESTREO"

        p_clip = np.clip(probs, 1e-6, 1.0 - 1e-6)
        ll_mod = ys * np.log(p_clip) + (1.0 - ys) * np.log(1.0 - p_clip)
        ll_clim = np.log(0.5)
        delta_ll = ll_mod - ll_clim
        s_val = 0.0
        s_max = 0.0
        for d_i in delta_ll:
            s_val = max(0.0, s_val + (-float(d_i) - k_holgura))
            s_max = max(s_max, s_val)
        alarma = bool(s_val >= h_alarma)
        out[str(mod_id)] = {
            "n_resueltas_oficial_t5": n_nom,
            "aciertos_direccionales": hits,
            "tasa_acierto_pct": round(100.0 * hits / n_nom, 2),
            "llr_nominal": round(llr_nom, 6),
            "estado_sprt": est_sprt,
            "cusum_actual_nats": round(s_val, 6),
            "cusum_max_historico_nats": round(s_max, 6),
            "alarma_cusum_activa": alarma,
            "estado_cusum": "ALARMA_DEGRADACION_ACTIVA" if alarma else "OPERACION_NORMAL_ESTABLE",
        }
    return out


# Columnas de resolución: únicas que pueden actualizarse después de la emisión.
COLUMNAS_RESOLUCION_GOLD = (
    "estado_resolucion",
    "sesiones_transcurridas",
    "fecha_parcial_reciente",
    "ppp_parcial_reciente",
    "retorno_parcial_pct",
    "acierto_parcial_en_curso",
    "ppp_t5_observado",
    "target_y_observado",
    "acierto_direccional_t5",
    "brier_observado_t5",
)


def _a_bool_o_none(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1"):
            return True
        if s in ("false", "0"):
            return False
        return None
    return bool(v)


def fusionar_gold_append_only(df_prev: pd.DataFrame, df_nuevas: pd.DataFrame) -> pd.DataFrame:
    """
    Fusiona la bitácora Gold respetando el pre-registro (Fase 0):
      * Señales nuevas (`id_senal_g2` inexistente) se anexan tal cual.
      * Señales ya emitidas conservan INMUTABLES todos sus campos de emisión
        (probabilidad, clase, features, timestamp). Solo se actualizan las
        columnas de `COLUMNAS_RESOLUCION_GOLD`, y los aciertos/Brier se
        recalculan con la predicción ORIGINAL registrada.
    """
    if df_prev is None or df_prev.empty:
        return df_nuevas.reset_index(drop=True)
    if df_nuevas is None or df_nuevas.empty:
        return df_prev.reset_index(drop=True)

    prev = df_prev.drop_duplicates(subset=["id_senal_g2"], keep="first").set_index("id_senal_g2")
    nuevas = df_nuevas.drop_duplicates(subset=["id_senal_g2"], keep="last").set_index("id_senal_g2")
    for col in nuevas.columns:
        if col not in prev.columns:
            prev[col] = None
    prev = prev.astype(object)

    ids_existentes = nuevas.index.intersection(prev.index)
    ids_nuevos = nuevas.index.difference(prev.index)

    for sid in ids_existentes:
        fila_n = nuevas.loc[sid]
        for col in COLUMNAS_RESOLUCION_GOLD:
            if col in nuevas.columns:
                val = fila_n[col]
                prev.at[sid, col] = None if (isinstance(val, float) and np.isnan(val)) else val

        # Recalcular aciertos con la predicción original (no la re-inferida)
        try:
            clase_orig = int(float(prev.at[sid, "prediccion_clase"]))
            prob_orig = float(prev.at[sid, "probabilidad_subida"])
        except (TypeError, ValueError, KeyError):
            continue
        ppp_t = pd.to_numeric(prev.at[sid, "ppp_base_t"], errors="coerce")
        ppp_par = pd.to_numeric(prev.at[sid, "ppp_parcial_reciente"], errors="coerce")
        if pd.notna(ppp_t) and pd.notna(ppp_par):
            prev.at[sid, "acierto_parcial_en_curso"] = bool(clase_orig == int(ppp_par > ppp_t))
        else:
            prev.at[sid, "acierto_parcial_en_curso"] = None
        y_obs = pd.to_numeric(prev.at[sid, "target_y_observado"], errors="coerce")
        if pd.notna(y_obs):
            y_i = int(y_obs)
            prev.at[sid, "acierto_direccional_t5"] = bool(clase_orig == y_i)
            prev.at[sid, "brier_observado_t5"] = round(float((prob_orig - y_i) ** 2), 6)
        else:
            prev.at[sid, "acierto_direccional_t5"] = None
            prev.at[sid, "brier_observado_t5"] = None

    comb = pd.concat([prev, nuevas.loc[ids_nuevos].astype(object)], axis=0)
    comb.index.name = "id_senal_g2"
    comb = comb.reset_index()
    orden_cols = list(df_prev.columns) + [c for c in df_nuevas.columns if c not in df_prev.columns]
    comb = comb[[c for c in orden_cols if c in comb.columns]]
    for col in comb.columns:
        es_float_prev = col in df_prev.columns and pd.api.types.is_float_dtype(df_prev[col].dtype)
        es_float_nuev = col in df_nuevas.columns and pd.api.types.is_float_dtype(df_nuevas[col].dtype)
        if es_float_prev or es_float_nuev:
            comb[col] = pd.to_numeric(comb[col], errors="coerce")
    return comb


def actualizar_resolucion_pendientes(
    df_gold: pd.DataFrame,
    df_serie: pd.DataFrame,
    df_eventos: pd.DataFrame | None = None,
    max_sesiones_contingencia: int = MAX_SESIONES_RECONCILIACION_CONTINGENCIA,
) -> pd.DataFrame:
    """
    Recalcula el seguimiento parcial y la resolución t+5 de TODAS las señales
    no resueltas de la bitácora contra `df_serie`, sin tocar campos de emisión.
    Así las señales de fechas que no están en la cola del día también se resuelven.
    Si `fecha_objetivo_h5` cae en un día inhábil BMV (error de calendario previo),
    se corrige a la sesión BMV válida.
    Aplica higiene de etiquetas por dividendos/splits (P3) y expira contingencias
    más antiguas que `max_sesiones_contingencia` sesiones BMV (P6).
    """
    if df_gold is None or df_gold.empty or df_serie is None or df_serie.empty:
        return df_gold
    out = df_gold.copy().astype(object)
    serie = df_serie.copy()
    serie["fecha"] = serie["fecha"].astype(str)
    serie["ppp_bmv_mxn"] = pd.to_numeric(serie["ppp_bmv_mxn"], errors="coerce")
    if "estado_captura" not in serie.columns:
        serie["estado_captura"] = "PPP_PUBLICADO_VERIFICADO"
    serie = serie.dropna(subset=["ppp_bmv_mxn"])
    if serie.empty:
        return out
    fecha_max_serie = str(serie["fecha"].max())[:10]
    por_emisora = {em: g.sort_values("fecha") for em, g in serie.groupby("emisora")}

    for idx in out.index:
        if str(out.at[idx, "estado_resolucion"]) in ("RESUELTA_OFICIAL_T5", "CONTINGENCIA_DEFINITIVA_EXCLUIDA"):
            continue
        em = str(out.at[idx, "emisora"])
        f_iso = str(out.at[idx, "fecha_senal"])[:10]
        h5 = str(out.at[idx, "fecha_objetivo_h5"])[:10]
        try:
            if not es_sesion_bmv(h5):
                h5 = calcular_fecha_h5(f_iso)
                out.at[idx, "fecha_objetivo_h5"] = h5
            clase_orig = int(float(out.at[idx, "prediccion_clase"]))
            prob_orig = float(out.at[idx, "probabilidad_subida"])
            ppp_t = float(out.at[idx, "ppp_base_t"])
        except (TypeError, ValueError):
            continue
        g = por_emisora.get(em)
        if g is None or not np.isfinite(ppp_t) or ppp_t <= 0:
            continue

        fut = g[(g["fecha"] > f_iso) & (g["fecha"] <= h5)]
        if not fut.empty:
            ppp_par = float(fut.iloc[-1]["ppp_bmv_mxn"])
            f_par = str(fut.iloc[-1]["fecha"])
            ppp_par_adj = calcular_ppp_t5_ajustado_dividendo(em, f_iso, f_par, ppp_par, df_eventos)
            out.at[idx, "fecha_parcial_reciente"] = f_par
            out.at[idx, "ppp_parcial_reciente"] = ppp_par
            out.at[idx, "retorno_parcial_pct"] = round((ppp_par_adj / ppp_t - 1.0) * 100.0, 4)
            out.at[idx, "acierto_parcial_en_curso"] = bool(clase_orig == int(ppp_par_adj > ppp_t))
            sesiones = int(len(fut))
        else:
            sesiones = 0
        out.at[idx, "sesiones_transcurridas"] = sesiones

        fila_h5 = g[g["fecha"] == h5]
        if not fila_h5.empty:
            base = g[g["fecha"] == f_iso]
            est_base = str(base.iloc[0]["estado_captura"]) if not base.empty else "PPP_PUBLICADO_VERIFICADO"
            est_h5 = str(fila_h5.iloc[0]["estado_captura"])
            if "CONTINGENCIA" in est_base or "CONTINGENCIA" in est_h5:
                ses_desde_h5 = contar_sesiones_bmv_entre(h5, fecha_max_serie)
                if ses_desde_h5 > max_sesiones_contingencia:
                    out.at[idx, "estado_resolucion"] = "CONTINGENCIA_DEFINITIVA_EXCLUIDA"
                else:
                    out.at[idx, "estado_resolucion"] = "PENDIENTE_RECONCILIACION"
                out.at[idx, "ppp_t5_observado"] = None
                out.at[idx, "target_y_observado"] = None
                out.at[idx, "acierto_direccional_t5"] = None
                out.at[idx, "brier_observado_t5"] = None
            else:
                ppp_t5 = float(fila_h5.iloc[0]["ppp_bmv_mxn"])
                ppp_t5_adj = calcular_ppp_t5_ajustado_dividendo(em, f_iso, h5, ppp_t5, df_eventos)
                y = int(ppp_t5_adj > ppp_t)
                out.at[idx, "estado_resolucion"] = "RESUELTA_OFICIAL_T5"
                out.at[idx, "ppp_t5_observado"] = ppp_t5
                out.at[idx, "target_y_observado"] = y
                out.at[idx, "acierto_direccional_t5"] = bool(clase_orig == y)
                out.at[idx, "brier_observado_t5"] = round(float((prob_orig - y) ** 2), 6)
        else:
            out.at[idx, "estado_resolucion"] = f"EN_CURSO_T+{sesiones}" if sesiones > 0 else "PENDIENTE_T+5"
    return out


def inferir_modelo_g2_v4_f1_gap(
    emisora: str,
    ret_1_rel: float,
    dm_5: float,
    dm_5_rel: float,
    vol_20: float,
    gap_uh_ppp: float,
    modo_corte: str = "HISTORIA_PURGADA_HASTA_CORTE",
    config_modelos: dict | None = None,
) -> dict:
    """
    Evalúa el modelo campeón de Fase 3 y Fase 5 (`G2_V4_F1_GAP`) con precisión doble.
    Soporta tanto el corte prospectivo (`G2_V4_F1_GAP`) como el corte de TRAIN
    congelado (`G2_V4_F1_GAP_CORTE_TRAIN`).
    """
    reg = config_modelos if config_modelos is not None else cargar_registro_modelos_g2()
    clave = (
        "G2_V4_F1_GAP_CORTE_TRAIN"
        if modo_corte == "TRAIN_CONGELADO" and "G2_V4_F1_GAP_CORTE_TRAIN" in reg
        else "G2_V4_F1_GAP"
    )
    cfg = reg.get(clave, MODELOS_G2_CONFIG["G2_V4_F1_GAP"])
    b = np.array(cfg["beta"], dtype=float)
    scalers_map = cfg.get("scalers", cfg.get("scalers_por_emisora", {}))
    sc = scalers_map.get(
        emisora,
        cfg.get("scaler_global_respaldo", scalers_map.get("WALMEX")),
    )
    m_vec = np.array(sc["mean"], dtype=float)
    s_vec = np.array(sc["scale"], dtype=float)
    x_in = np.array([ret_1_rel, dm_5, dm_5_rel, vol_20, gap_uh_ppp], dtype=float)
    x_s = (x_in - m_vec) / s_vec
    x_aug = np.append(1.0, x_s)
    logit = float(np.clip(np.dot(b, x_aug), -35.0, 35.0))
    p = float(1.0 / (1.0 + np.exp(-logit)))
    clase = int(p >= 0.5)
    return {
        "probabilidad": p,
        "clase": clase,
        "etiqueta": "SUBIDA" if clase == 1 else "NO_SUBIDA",
    }


def inferir_modelos_g2(
    emisora: str,
    ret_10: float,
    ret_10_rel: float,
    vol_20: float,
    ret_1_rel: float = 0.0,
    dm_5: float = 0.0,
    dm_5_rel: float = 0.0,
    ret_5: float = 0.0,
    ret_20: float = 0.0,
    dm_20: float = 0.0,
    gap_uh_ppp: float | None = None,
    incluir_challenger_f1: bool = False,
    config_modelos: dict | None = None,
) -> tuple[dict, str]:
    reg = config_modelos if config_modelos is not None else cargar_registro_modelos_g2()
    x_raw_rel3 = np.array([ret_10, ret_10_rel, vol_20], dtype=float)
    x_raw_dm5 = np.array([ret_1_rel, dm_5, dm_5_rel, vol_20], dtype=float)
    res = {}
    preds = []

    for id_mod in [
        "G2_V1_POOLED_REL3_CALIBRADO",
        "G2_V2_POOLED_REL3_ZONA_NEUTRAL",
        "G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO",
        "G2_V4_POOLED_DM5_REL_CORTO_PLAZO",
    ]:
        cfg = reg[id_mod]
        b = np.array(cfg["beta"], dtype=float)
        scalers_map = cfg.get("scalers", cfg.get("scalers_por_emisora", {}))
        sc = scalers_map.get(emisora, scalers_map["WALMEX"])
        m_vec = np.array(sc["mean"], dtype=float)
        s_vec = np.array(sc["scale"], dtype=float)
        x_in = x_raw_dm5 if id_mod == "G2_V4_POOLED_DM5_REL_CORTO_PLAZO" else x_raw_rel3
        x_s = (x_in - m_vec) / s_vec
        x_aug = np.append(1.0, x_s)
        logit = float(np.clip(np.dot(b, x_aug), -35.0, 35.0))
        p = float(1.0 / (1.0 + np.exp(-logit)))
        clase = int(p >= 0.5)
        preds.append(clase)
        res[id_mod] = {
            "probabilidad": p,
            "clase": clase,
            "etiqueta": "SUBIDA" if clase == 1 else "NO_SUBIDA",
        }

    # Modelo G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL
    p_dm5 = res["G2_V4_POOLED_DM5_REL_CORTO_PLAZO"]["probabilidad"]
    p_rel3 = res["G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO"]["probabilidad"]
    cfg_v5 = reg["G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL"]

    if emisora == "AMX":
        x_loc = np.array([ret_5, ret_20, dm_5, dm_20, ret_10_rel, vol_20], dtype=float)
        m_loc = np.array(cfg_v5["amx_momentum_mean"], dtype=float)
        s_loc = np.array(cfg_v5["amx_momentum_scale"], dtype=float)
        b_loc = np.array(cfg_v5["amx_momentum_beta"], dtype=float)
        x_loc_aug = np.append(1.0, (x_loc - m_loc) / s_loc)
        logit_loc = float(np.clip(np.dot(b_loc, x_loc_aug), -35.0, 35.0))
        p_loc = float(1.0 / (1.0 + np.exp(-logit_loc)))
        p_v5 = float(0.65 * p_loc + 0.35 * p_dm5)
    else:
        p_base = 0.85 * p_dm5 + 0.15 * p_rel3
        if dm_20 < -0.002 and ret_10_rel < -0.055:
            p_v5 = p_base - 0.055
        elif ret_10 > 0.028 and ret_10_rel > 0.015 and ret_5 > -0.015:
            p_v5 = min(p_base, p_rel3) - 0.006
        elif dm_20 > 0.005 and ret_5 < 0.0 and ret_10_rel < 0.0:
            p_v5 = max(p_base, p_rel3) + 0.006
        else:
            p_v5 = p_base
        p_v5 = float(np.clip(p_v5, 0.05, 0.95))

    clase_v5 = int(p_v5 >= 0.5)
    preds.append(clase_v5)
    res["G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL"] = {
        "probabilidad": p_v5,
        "clase": clase_v5,
        "etiqueta": "SUBIDA" if clase_v5 == 1 else "NO_SUBIDA",
    }

    if incluir_challenger_f1 and gap_uh_ppp is not None:
        res["G2_V4_F1_GAP"] = inferir_modelo_g2_v4_f1_gap(
            emisora=emisora,
            ret_1_rel=ret_1_rel,
            dm_5=dm_5,
            dm_5_rel=dm_5_rel,
            vol_20=vol_20,
            gap_uh_ppp=gap_uh_ppp,
            config_modelos=reg,
        )

    if all(c == 1 for c in preds):
        consenso = "CONSENSO_PANEL_G2_SUBIDA"
    elif all(c == 0 for c in preds):
        consenso = "CONSENSO_PANEL_G2_NO_SUBIDA"
    else:
        consenso = (
            f"DIVERGENCIA_G2 (V1={res['G2_V1_POOLED_REL3_CALIBRADO']['etiqueta']}, "
            f"V2={res['G2_V2_POOLED_REL3_ZONA_NEUTRAL']['etiqueta']}, "
            f"V3={res['G2_V3_POOLED_REL3_ALTA_DISC_EXPANDIDO']['etiqueta']}, "
            f"V4={res['G2_V4_POOLED_DM5_REL_CORTO_PLAZO']['etiqueta']}, "
            f"V5={res['G2_V5_ADAPTATIVO_REGIMEN_SECTORIAL']['etiqueta']})"
        )

    return res, consenso


def _procesar_fecha_en_s3(s3, fecha_str: str) -> tuple[pd.DataFrame, dict]:
    """
    Procesa una sesión bursátil con prioridad en Fuente Primaria BMV (HTML RSS)
    y fallback automático a Fuente Secundaria de Contingencia (VWAP 13:40-14:00 CDMX).
    Nunca sobrescribe en S3 un archivo que ya tenga estado PPP_PUBLICADO_VERIFICADO
    con datos de contingencia.
    """
    fecha_iso = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    url_boletin = f"https://www.bmv.com.mx/docs-pub/rss/boletin{fecha_str}.html"
    silver_key = f"silver/precios_ppp/{fecha_str[:4]}/{fecha_str[4:6]}/ppp_15_emisoras_{fecha_str}.csv"

    print(f"[{fecha_iso}] Consultando fuente primaria BMV: {url_boletin}")
    raw_html_bytes = None
    try:
        req = urllib.request.Request(
            url_boletin, headers={"User-Agent": "Mozilla/5.0 PrismaBMV-CloudML/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_html_bytes = response.read()
    except Exception as e_prim:
        print(f"[{fecha_iso}] Fuente primaria no disponible ({e_prim}). Evaluando contingencia...")

    if raw_html_bytes is not None:
        sha256_fuente = hashlib.sha256(raw_html_bytes).hexdigest()
        url_fuente = url_boletin
        estado_captura_ok = "PPP_PUBLICADO_VERIFICADO"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.html",
            Body=raw_html_bytes,
            ContentType="text/html",
        )
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/boletin_{fecha_str}.sha256",
            Body=sha256_fuente.encode("utf-8"),
            ContentType="text/plain",
        )
        quotes = parse_bulletin_quotes(raw_html_bytes)
    else:
        # Si ya existe en S3 una captura primaria verificada para esta fecha, conservarla intacta
        try:
            obj_prev = s3.get_object(Bucket=BUCKET_NAME, Key=silver_key)
            df_prev = pd.read_csv(io.BytesIO(obj_prev["Body"].read()))
            if "estado_captura" in df_prev.columns and (df_prev["estado_captura"] == "PPP_PUBLICADO_VERIFICADO").any():
                print(f"[{fecha_iso}] S3 ya cuenta con PPP_PUBLICADO_VERIFICADO; se preserva intacto.")
                return df_prev, {
                    "fecha": fecha_iso,
                    "fuente": "PRIMARIA_PREVIA_PRESERVADA",
                    "sha256": str(df_prev["sha256_boletin"].dropna().iloc[0]) if "sha256_boletin" in df_prev.columns else "",
                }
        except Exception:
            pass

        quotes, raw_json_bytes, sha256_fuente, url_fuente = fetch_secondary_contingency_quotes(fecha_iso)
        if not quotes:
            raise RuntimeError(f"Sin datos primarios ni secundarios para {fecha_iso}")
        estado_captura_ok = "CONTINGENCIA_FUENTE_SECUNDARIA"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/contingencia_{fecha_str}.json",
            Body=raw_json_bytes,
            ContentType="application/json",
        )
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"bronze/{fecha_str[:4]}/{fecha_str[4:6]}/contingencia_{fecha_str}.sha256",
            Body=sha256_fuente.encode("utf-8"),
            ContentType="text/plain",
        )

    registros_silver = []
    for ticker, serie, anillo, sector in EMISORAS_15:
        q = quotes.get((ticker, serie))
        if q is not None:
            ev_str = (
                f"{ticker} / {serie} / PPP / {q['ppp']:.2f}"
                if estado_captura_ok == "PPP_PUBLICADO_VERIFICADO"
                else f"{ticker} / {serie} / VWAP_CONTINGENCIA_1340_1400 / {q['ppp']:.2f}"
            )
            registros_silver.append({
                "fecha": fecha_iso,
                "emisora": ticker,
                "serie": serie,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "estado_captura": estado_captura_ok,
                "ppp_bmv_mxn": q["ppp"],
                "ultimo_bmv_mxn": q["ultimo"],
                "anterior_bmv_mxn": q["anterior"],
                "variacion_ppp_vs_anterior_pct": q["variacion_ppp_vs_anterior_pct"],
                "evidencia_exacta": ev_str,
                "url_fuente": url_fuente,
                "sha256_boletin": sha256_fuente,
            })
        else:
            registros_silver.append({
                "fecha": fecha_iso,
                "emisora": ticker,
                "serie": serie,
                "anillo_madurez": anillo,
                "sector_economico": sector,
                "estado_captura": "NO_PUBLICADA_EN_BOLETIN_RSS_DEL_DIA",
                "ppp_bmv_mxn": None,
                "ultimo_bmv_mxn": None,
                "anterior_bmv_mxn": None,
                "variacion_ppp_vs_anterior_pct": None,
                "evidencia_exacta": "Ausente del boletin; cero imputacion",
                "url_fuente": url_fuente,
                "sha256_boletin": sha256_fuente,
            })

    df_silver = pd.DataFrame(registros_silver)
    csv_bytes = df_silver.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=silver_key,
        Body=csv_bytes,
        ContentType="text/csv",
    )
    return df_silver, {
        "fecha": fecha_iso,
        "fuente": estado_captura_ok,
        "sha256": sha256_fuente,
        "emisoras_capturadas": int(df_silver["ppp_bmv_mxn"].notna().sum()),
    }


def lambda_handler(event, context):
    s3 = boto3.client("s3")

    # 1. Determinar fecha objetivo
    if event and isinstance(event, dict) and "fecha" in event:
        fecha_str = str(event["fecha"]).replace("-", "")
    else:
        cdmx_tz = datetime.timezone(datetime.timedelta(hours=-6))
        ahora = datetime.datetime.now(cdmx_tz)
        fecha_str = ahora.strftime("%Y%m%d")
    fecha_iso_obj = f"{fecha_str[:4]}-{fecha_str[4:6]}-{fecha_str[6:]}"
    tiene_fechas_explicitas = bool(
        event and isinstance(event, dict) and isinstance(event.get("fechas"), list) and event["fechas"]
    )

    # 1b. Guardia de calendario: no se emite ni descarga nada en días inhábiles BMV
    if not es_sesion_bmv(fecha_iso_obj) and not tiene_fechas_explicitas:
        print(f"[{fecha_iso_obj}] No es sesion BMV (fin de semana o feriado oficial). Sin ejecucion.")
        return {
            "statusCode": 200,
            "body": json.dumps({"estado": "SIN_SESION_BMV", "fecha": fecha_iso_obj}),
        }
    # 2. Cargar serie histórica de S3 para construir cola de reconciliación retroactiva
    try:
        obj_hist = s3.get_object(Bucket=BUCKET_NAME, Key="silver/serie_unificada_reciente.csv")
        df_hist = pd.read_csv(io.BytesIO(obj_hist["Body"].read()))
    except Exception:
        df_hist = pd.DataFrame(columns=["fecha", "emisora", "ppp_bmv_mxn", "estado_captura"])

    cola_fechas = []
    fechas_contingencia_expiradas = set()
    if not df_hist.empty and "estado_captura" in df_hist.columns and "fecha" in df_hist.columns:
        fechas_contingencia = sorted(
            df_hist[df_hist["estado_captura"] == "CONTINGENCIA_FUENTE_SECUNDARIA"]["fecha"]
            .dropna()
            .astype(str)
            .unique()
        )
        for f_iso in fechas_contingencia:
            f_clean = f_iso.replace("-", "")
            if len(f_clean) == 8 and f_clean <= fecha_str:
                ses_antiguedad = contar_sesiones_bmv_entre(f_iso[:10], fecha_iso_obj)
                if ses_antiguedad <= MAX_SESIONES_RECONCILIACION_CONTINGENCIA:
                    if f_clean not in cola_fechas:
                        cola_fechas.append(f_clean)
                else:
                    fechas_contingencia_expiradas.add(f_iso[:10])

    if event and isinstance(event, dict) and "fechas" in event and isinstance(event["fechas"], list):
        for f_item in event["fechas"]:
            f_clean = str(f_item).replace("-", "")
            if len(f_clean) == 8 and f_clean not in cola_fechas:
                cola_fechas.append(f_clean)

    if fecha_str not in cola_fechas and es_sesion_bmv(fecha_iso_obj):
        cola_fechas.append(fecha_str)
    cola_fechas = sorted(
        f for f in cola_fechas if es_sesion_bmv(f"{f[:4]}-{f[4:6]}-{f[6:]}")
    )
    print(f"Cola de ejecucion y reconciliacion S3: {cola_fechas}")

    # 3. Procesar cada fecha en la cola (Primaria -> Fallback Secundario -> Reconciliación)
    dfs_procesados = {}
    resumen_fechas = []
    for f_str in cola_fechas:
        try:
            df_sil, meta_f = _procesar_fecha_en_s3(s3, f_str)
            dfs_procesados[f_str] = df_sil
            resumen_fechas.append(meta_f)
        except Exception as e_f:
            print(f"Aviso en fecha {f_str}: {e_f}")

    if not dfs_procesados:
        # Día hábil BMV sin datos primarios ni secundarios: falla real -> invocación fallida
        raise RuntimeError(f"ERROR_PRISMA_CRITICO: ERROR_DESCARGA sin datos para {cola_fechas}")

    # 4. Actualizar serie unificada y ejecutar inferencia IA (Capa Gold - Modelos G2)
    print("Iniciando inferencia predictiva de Inteligencia Artificial (Panel G2)...")
    resumen_ia = {}
    resumen_ia_f1_gap = {}
    VALID_CAPTURE_STATES = {
        "PPP_PUBLICADO_VERIFICADO",
        "CONTINGENCIA_FUENTE_SECUNDARIA",
        "CONTINGENCIA_DEFINITIVA_EXCLUIDA",
    }
    errores_criticos = []
    df_serie_guardable = None

    try:
        df_serie = df_hist.copy()
        if "estado_captura" not in df_serie.columns:
            df_serie["estado_captura"] = "PPP_PUBLICADO_VERIFICADO"
        if fechas_contingencia_expiradas and not df_serie.empty:
            mask_exp = (
                df_serie["fecha"].astype(str).str[:10].isin(fechas_contingencia_expiradas)
                & (df_serie["estado_captura"] == "CONTINGENCIA_FUENTE_SECUNDARIA")
            )
            df_serie.loc[mask_exp, "estado_captura"] = "CONTINGENCIA_DEFINITIVA_EXCLUIDA"

        cols_serie_opc = ["ultimo_bmv_mxn", "sha256_boletin", "url_fuente"]
        for c_op in cols_serie_opc:
            if c_op not in df_serie.columns:
                df_serie[c_op] = None

        for f_str, df_sil in sorted(dfs_procesados.items()):
            f_iso = f"{f_str[:4]}-{f_str[4:6]}-{f_str[6:]}"
            cols_presentes = [
                c
                for c in ["fecha", "emisora", "ppp_bmv_mxn", "ultimo_bmv_mxn", "estado_captura", "sha256_boletin", "url_fuente"]
                if c in df_sil.columns
            ]
            df_dia_val = df_sil[df_sil["estado_captura"].isin(VALID_CAPTURE_STATES)][
                cols_presentes
            ].dropna(subset=["ppp_bmv_mxn"])

            if df_dia_val.empty:
                continue

            es_primaria = (df_dia_val["estado_captura"] == "PPP_PUBLICADO_VERIFICADO").any()
            ya_tenia_primaria = (
                not df_serie.empty
                and ((df_serie["fecha"] == f_iso) & (df_serie["estado_captura"] == "PPP_PUBLICADO_VERIFICADO")).any()
            )
            if ya_tenia_primaria and not es_primaria:
                continue

            # Reemplazar registros previos de esa fecha (promoviendo contingencia -> primaria o actualizando)
            df_serie = df_serie[df_serie["fecha"] != f_iso]
            df_serie = pd.concat([df_serie, df_dia_val], ignore_index=True)

        df_serie = df_serie.drop_duplicates(subset=["fecha", "emisora"], keep="last")
        df_serie = df_serie.sort_values(["emisora", "fecha"]).reset_index(drop=True)
        df_serie_guardable = df_serie

        emisoras_panel = ["AMX", "FEMSA", "GFNORTE", "GMEXICO", "WALMEX"]
        filas_gold_nuevas = []
        config_modelos_s3 = cargar_registro_modelos_g2(s3_client=s3, bucket_name=BUCKET_NAME)
        df_eventos_corp = cargar_eventos_corporativos_s3_o_local(s3_client=s3, bucket_name=BUCKET_NAME)
        ts_emision_lote = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for f_str in sorted(dfs_procesados.keys()):
            f_iso = f"{f_str[:4]}-{f_str[4:6]}-{f_str[6:]}"
            df_corte = df_serie[df_serie["fecha"] <= f_iso]
            fechas_corte_disp = sorted(df_corte["fecha"].dropna().astype(str).unique().tolist())
            fechas_21 = fechas_corte_disp[-21:] if len(fechas_corte_disp) >= 21 else []
            rets_1_hoy = {}
            rets_5_hoy = {}
            rets_10_hoy = {}
            rets_20_hoy = {}
            dm_5_hoy = {}
            dm_20_hoy = {}
            vols_20_hoy = {}
            precios_hoy = {}
            ultimos_hoy = {}
            sha256_hoy = {}
            url_hoy = {}
            estados_captura_hoy = {}

            for em in emisoras_panel:
                if len(fechas_21) < 21 or fechas_21[-1] != f_iso:
                    continue
                sub = (
                    df_corte[df_corte["emisora"] == em]
                    .sort_values("fecha")
                    .drop_duplicates("fecha", keep="last")
                    .set_index("fecha")
                    .reindex(fechas_21)
                )
                precios_21 = sub["ppp_bmv_mxn"].to_numpy(dtype=float)
                if int(np.sum(np.isfinite(precios_21) & (precios_21 > 0))) == 21:
                    fila_f = sub.loc[f_iso]
                    estados_captura_hoy[em] = str(
                        fila_f.get("estado_captura", "PPP_PUBLICADO_VERIFICADO")
                    )
                    ult_val = pd.to_numeric(fila_f.get("ultimo_bmv_mxn"), errors="coerce")
                    ultimos_hoy[em] = float(ult_val) if pd.notna(ult_val) else None
                    sha_v = fila_f.get("sha256_boletin")
                    sha256_hoy[em] = str(sha_v) if pd.notna(sha_v) and sha_v is not None else ""
                    url_v = fila_f.get("url_fuente")
                    url_hoy[em] = str(url_v) if pd.notna(url_v) and url_v is not None else ""
                    precios_hoy[em] = float(precios_21[-1])
                    rets_1_hoy[em] = float(precios_21[-1] / precios_21[-2] - 1.0)
                    rets_5_hoy[em] = float(precios_21[-1] / precios_21[-6] - 1.0)
                    rets_10_hoy[em] = float(precios_21[-1] / precios_21[-11] - 1.0)
                    rets_20_hoy[em] = float(precios_21[-1] / precios_21[0] - 1.0)
                    dm_5_hoy[em] = float(precios_21[-1] / np.mean(precios_21[-5:]) - 1.0)
                    dm_20_hoy[em] = float(precios_21[-1] / np.mean(precios_21[-20:]) - 1.0)
                    rets_1_seq = precios_21[1:] / precios_21[:-1] - 1.0
                    vols_20_hoy[em] = float(np.std(rets_1_seq[-20:], ddof=1))

            if len(rets_10_hoy) >= 2:
                media_panel_10 = float(np.mean(list(rets_10_hoy.values())))
                media_panel_1 = float(np.mean(list(rets_1_hoy.values())))
                media_panel_dm5 = float(np.mean(list(dm_5_hoy.values())))
            else:
                media_panel_10 = 0.0
                media_panel_1 = 0.0
                media_panel_dm5 = 0.0

            fecha_obj_h5 = calcular_fecha_h5(f_iso)
            ini_v21 = fechas_21[0] if len(fechas_21) == 21 else ""
            fin_v21 = fechas_21[-1] if len(fechas_21) == 21 else f_iso

            for em in emisoras_panel:
                if em not in rets_10_hoy or em not in vols_20_hoy:
                    continue
                r10 = rets_10_hoy[em]
                r10_rel = float(r10 - media_panel_10)
                r1_rel = float(rets_1_hoy[em] - media_panel_1)
                dm5 = dm_5_hoy[em]
                dm5_rel = float(dm5 - media_panel_dm5)
                r5 = rets_5_hoy[em]
                r20 = rets_20_hoy[em]
                dm20 = dm_20_hoy[em]
                v20 = vols_20_hoy[em]
                ppp_t = precios_hoy[em]
                gap_val = calcular_gap_uh_ppp(ultimos_hoy.get(em), ppp_t)

                predicciones, consenso_str = inferir_modelos_g2(
                    em,
                    r10,
                    r10_rel,
                    v20,
                    ret_1_rel=r1_rel,
                    dm_5=dm5,
                    dm_5_rel=dm5_rel,
                    ret_5=r5,
                    ret_20=r20,
                    dm_20=dm20,
                    gap_uh_ppp=gap_val,
                    incluir_challenger_f1=(gap_val is not None),
                    config_modelos=config_modelos_s3,
                )
                if f_str == fecha_str:
                    resumen_ia[em] = consenso_str
                    if "G2_V4_F1_GAP" in predicciones:
                        resumen_ia_f1_gap[em] = predicciones["G2_V4_F1_GAP"]

                # Seguimiento parcial y resolución oficial t+5 contra df_serie (con ajuste por dividendos Fase 1)
                sub_futuro = df_serie[
                    (df_serie["emisora"] == em)
                    & (df_serie["fecha"] > f_iso)
                    & (df_serie["fecha"] <= fecha_obj_h5)
                    & (df_serie["ppp_bmv_mxn"].notna())
                ].sort_values("fecha")

                if not sub_futuro.empty:
                    ult_fila = sub_futuro.iloc[-1]
                    fecha_parcial = str(ult_fila["fecha"])
                    ppp_parcial = float(ult_fila["ppp_bmv_mxn"])
                    ppp_parcial_adj = calcular_ppp_t5_ajustado_dividendo(
                        em, f_iso, fecha_parcial, ppp_parcial, df_eventos_corp
                    )
                    ret_parcial_pct = round(float((ppp_parcial_adj / ppp_t - 1.0) * 100.0), 4)
                    dir_parcial = int(ppp_parcial_adj > ppp_t)
                    sesiones_trans = int(len(sub_futuro))
                else:
                    fecha_parcial = "PENDIENTE"
                    ppp_parcial = None
                    ret_parcial_pct = None
                    dir_parcial = None
                    sesiones_trans = 0

                fila_h5 = df_serie[
                    (df_serie["emisora"] == em)
                    & (df_serie["fecha"] == fecha_obj_h5)
                    & (df_serie["ppp_bmv_mxn"].notna())
                ]
                if not fila_h5.empty:
                    est_base = estados_captura_hoy.get(em, "PPP_PUBLICADO_VERIFICADO")
                    est_h5 = str(fila_h5.iloc[0].get("estado_captura", "PPP_PUBLICADO_VERIFICADO"))
                    if "CONTINGENCIA" in est_base or "CONTINGENCIA" in est_h5:
                        ppp_t5_obs = None
                        y_obs = None
                        ses_desde_h5 = contar_sesiones_bmv_entre(fecha_obj_h5, fecha_iso_obj)
                        estado_res = (
                            "CONTINGENCIA_DEFINITIVA_EXCLUIDA"
                            if ses_desde_h5 > MAX_SESIONES_RECONCILIACION_CONTINGENCIA
                            else "PENDIENTE_RECONCILIACION"
                        )
                    else:
                        ppp_t5_obs = float(fila_h5.iloc[0]["ppp_bmv_mxn"])
                        ppp_t5_adj = calcular_ppp_t5_ajustado_dividendo(
                            em, f_iso, fecha_obj_h5, ppp_t5_obs, df_eventos_corp
                        )
                        y_obs = int(ppp_t5_adj > ppp_t)
                        estado_res = "RESUELTA_OFICIAL_T5"
                else:
                    ppp_t5_obs = None
                    y_obs = None
                    estado_res = f"EN_CURSO_T+{sesiones_trans}" if sesiones_trans > 0 else "PENDIENTE_T+5"

                for id_mod, res_mod in predicciones.items():
                    clase_m = res_mod["clase"]
                    prob_m = res_mod["probabilidad"]
                    acierto_parcial = bool(clase_m == dir_parcial) if dir_parcial is not None else None
                    acierto_t5 = bool(clase_m == y_obs) if y_obs is not None else None
                    brier_t5 = round(float((prob_m - y_obs) ** 2), 6) if y_obs is not None else None
                    meta_m = META_ENTRENAMIENTO_G2.get(
                        id_mod,
                        {
                            "modo_entrenamiento": "HISTORIA_PURGADA_HASTA_CORTE",
                            "n_train_panel": 9679,
                            "fin_etiquetas_train_panel": "2026-10-28",
                        },
                    )
                    cfg_m = config_modelos_s3.get(id_mod, MODELOS_G2_CONFIG.get(id_mod, {}))

                    filas_gold_nuevas.append({
                        "id_senal_g2": f"G2_{f_str}_{em}_{id_mod}",
                        "generacion_modelo": "SEGUNDA_GENERACION_POOLED_PANEL_REL3",
                        "fecha_senal": f_iso,
                        "muestra_evaluacion": (
                            "IN_SAMPLE_DISENO"
                            if f_iso < FECHA_CONGELAMIENTO_G2
                            else "OUT_OF_SAMPLE_PRE_REGISTRADO"
                        ),
                        "fecha_objetivo_h5": fecha_obj_h5,
                        "calendario_objetivo": "OFICIAL_2026",
                        "emisora": em,
                        "serie": MAPA_SERIE_EMISORA.get(em, "B"),
                        "sector_economico": MAPA_SECTOR_EMISORA.get(em, ""),
                        "modelo_g2": id_mod,
                        "modo_entrenamiento": meta_m["modo_entrenamiento"],
                        "n_train_panel": meta_m["n_train_panel"],
                        "fin_etiquetas_train_panel": meta_m["fin_etiquetas_train_panel"],
                        "c_regularizacion": cfg_m.get("c_val", 0.01),
                        "tau_zona_neutral": cfg_m.get("tau_val", 0.0),
                        "ppp_base_t": ppp_t,
                        "ret_10": r10,
                        "media_ret_10_panel_corte": media_panel_10,
                        "ret_10_rel_panel": r10_rel,
                        "volatilidad_20": v20,
                        "probabilidad_subida": round(prob_m, 6),
                        "prediccion_clase": clase_m,
                        "prediccion_etiqueta": res_mod["etiqueta"],
                        "estado_consenso_g2": consenso_str,
                        "estado_resolucion": estado_res,
                        "sesiones_transcurridas": sesiones_trans,
                        "fecha_parcial_reciente": fecha_parcial,
                        "ppp_parcial_reciente": ppp_parcial,
                        "retorno_parcial_pct": ret_parcial_pct,
                        "acierto_parcial_en_curso": acierto_parcial,
                        "ppp_t5_observado": ppp_t5_obs,
                        "target_y_observado": y_obs,
                        "acierto_direccional_t5": acierto_t5,
                        "brier_observado_t5": brier_t5,
                        "inicio_ventana_21": ini_v21,
                        "fin_ventana_21": fin_v21,
                        "sha256_boletin_base": sha256_hoy.get(em, ""),
                        "url_fuente_base": url_hoy.get(em, ""),
                        "version_features": "PPP_V2_MEDIA20",
                        "version_metodologia": "PPP_EVALUACION_V2",
                        "version_monitor_g2": "MONITOR_PROSPECTIVO_PANEL_G2_V2_MULTIESCALA_SECTORIAL",
                        "timestamp_emision_utc": ts_emision_lote,
                    })

        # 5. Guardar en CAPA GOLD de S3 (append-only: emisiones inmutables)
        gold_key = "gold/senales_g2/registro_senales_prospectivas_panel_g2.csv"
        try:
            obj_gold = s3.get_object(Bucket=BUCKET_NAME, Key=gold_key)
            df_gold_prev = pd.read_csv(
                io.BytesIO(obj_gold["Body"].read()),
                float_precision="round_trip",
            )
        except Exception as e_gold:
            codigo = getattr(e_gold, "response", {}).get("Error", {}).get("Code", "")
            if codigo in ("NoSuchKey", "404"):
                df_gold_prev = pd.DataFrame()
            else:
                # Nunca sobrescribir la bitácora si no se pudo leer (evita pérdida de historial)
                raise RuntimeError(f"No se pudo leer Gold previo ({codigo or e_gold}); se aborta escritura") from e_gold

        if filas_gold_nuevas or not df_gold_prev.empty:
            df_nuevas = pd.DataFrame(filas_gold_nuevas)
            if not df_nuevas.empty and "timestamp_emision_utc" not in df_nuevas.columns:
                df_nuevas["timestamp_emision_utc"] = ts_emision_lote
            df_gold_comb = fusionar_gold_append_only(df_gold_prev, df_nuevas)
            df_gold_comb = actualizar_resolucion_pendientes(
                df_gold_comb, df_serie, df_eventos=df_eventos_corp
            )
            n_preservadas = (
                int(df_nuevas["id_senal_g2"].isin(df_gold_prev["id_senal_g2"]).sum())
                if (not df_nuevas.empty and not df_gold_prev.empty and "id_senal_g2" in df_gold_prev.columns)
                else 0
            )

            csv_gold = df_gold_comb.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            s3.put_object(Bucket=BUCKET_NAME, Key=gold_key, Body=csv_gold, ContentType="text/csv")
            # Emitir reporte semanal de monitoreo secuencial (CUSUM + SPRT reales, P7) en S3 Gold
            rep_semanal_key = f"gold/reportes/monitoreo_semanal_{fecha_str}.json"
            resueltas_df = df_gold_comb[df_gold_comb["estado_resolucion"] == "RESUELTA_OFICIAL_T5"]
            n_res = int(len(resueltas_df))
            monitoreo_modelos = calcular_monitoreo_secuencial_gold(df_gold_comb)
            rep_semanal_payload = {
                "fecha_reporte": fecha_iso_obj,
                "s3_key": rep_semanal_key,
                "total_senales_registradas": int(len(df_gold_comb)),
                "total_senales_resueltas_oficial_t5": n_res,
                "sprt_wald_config": {
                    "p0": 0.50,
                    "p1": 0.55,
                    "alpha": 0.05,
                    "beta": 0.20,
                    "n_independientes_requeridas_80pct": 617,
                },
                "cusum_page_config": {
                    "k_holgura_nats": 0.001,
                    "h_umbral_alarma_nats": 1.5,
                },
                "monitoreo_por_modelo": monitoreo_modelos,
            }
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=rep_semanal_key,
                Body=json.dumps(rep_semanal_payload, indent=2, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
            print(
                f"Capa Gold actualizada: {len(filas_gold_nuevas)} inferencias calculadas, "
                f"{n_preservadas} emisiones previas preservadas sin cambios, {rep_semanal_key}."
            )
    except Exception as e:
        errores_criticos.append(f"INFERENCIA_O_GOLD: {type(e).__name__}: {e}")
        print("ERROR_PRISMA_CRITICO inferencia/gold:\n" + traceback.format_exc())

    # 6. Guardar la serie actualizada en S3 aunque la inferencia haya fallado
    #    (incluye estado_captura para la cola de reconciliación de mañana)
    if df_serie_guardable is not None:
        try:
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key="silver/serie_unificada_reciente.csv",
                Body=df_serie_guardable.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                ContentType="text/csv",
            )
        except Exception as e_ser:
            errores_criticos.append(f"SERIE_UNIFICADA: {type(e_ser).__name__}: {e_ser}")
            print("ERROR_PRISMA_CRITICO serie_unificada:\n" + traceback.format_exc())

    resultado = {
        "estado": "EXITO_PROCESADO_E_INFERENCIA_IA" if not errores_criticos else "ERROR_INFERENCIA_IA",
        "cola_procesada": resumen_fechas,
        "inferencias_g2_generadas": len(resumen_ia),
        "consensos_fecha_objetivo": resumen_ia,
        "errores_criticos": errores_criticos,
        "s3_gold": f"s3://{BUCKET_NAME}/gold/senales_g2/registro_senales_prospectivas_panel_g2.csv",
    }
    print("Resumen de ejecución:", json.dumps(resultado, indent=2))

    if errores_criticos:
        # Lanzar excepción para que AWS registre la invocación como fallida
        # (métrica `Errors` de CloudWatch -> alarma). Nunca reportar EXITO con fallas.
        raise RuntimeError("ERROR_PRISMA_CRITICO: " + " | ".join(errores_criticos))

    return {"statusCode": 200, "body": json.dumps(resultado)}
