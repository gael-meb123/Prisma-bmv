"""Audita vínculos y estados de ventanas del panel local; no valida sus fórmulas."""
import argparse
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path


def cargar(path):
    raw = path.read_bytes()
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))), hashlib.sha256(raw).hexdigest()


def auditar(historico, panel):
    por_clave, por_posicion = {}, {}
    for r in historico:
        clave = (r["fecha"], r["emisora"], r["serie"])
        posicion = (int(r["posicion_sesion"]), r["emisora"], r["serie"])
        if clave in por_clave or posicion in por_posicion:
            raise ValueError("Histórico tiene claves o posiciones duplicadas.")
        por_clave[clave], por_posicion[posicion] = r, r
    contadores = collections.Counter()
    ventanas_incompletas = []
    claves_panel = set()
    for r in panel:
        clave = (r["fecha"], r["emisora"], r["serie"])
        if clave in claves_panel:
            raise ValueError("Panel tiene claves duplicadas.")
        claves_panel.add(clave)
        contadores["filas_panel"] += 1
        h = por_clave.get(clave)
        if not h:
            contadores["sin_vinculo_exacto"] += 1
            continue
        contadores["vinculo_exacto"] += 1
        if r["posicion_sesion"] != h["posicion_sesion"]:
            contadores["posicion_distinta"] += 1
            continue
        if h["estado_captura"] == "PPP_PUBLICADO_VERIFICADO":
            contadores["estado_base_verificado"] += 1
        try:
            a, b = float(r["ppp_t"]), float(h["ppp_bmv_mxn"])
            valido = math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0
            if not valido:
                raise ValueError()
            contadores["ppp_base_igual" if math.isclose(a, b, rel_tol=0, abs_tol=1e-8) else "ppp_base_distinto"] += 1
        except (TypeError, ValueError):
            contadores["ppp_base_faltante_o_invalido"] += 1
        posicion = int(r["posicion_sesion"])
        ventana = [por_posicion.get((posicion - n, r["emisora"], r["serie"])) for n in range(21)]
        verificada = all(x and x["estado_captura"] == "PPP_PUBLICADO_VERIFICADO" for x in ventana)
        contadores["ventana_21_estados_verificados" if verificada else "ventana_21_con_faltante_o_no_verificado"] += 1
        if not verificada:
            estados = collections.Counter(
                x["estado_captura"] if x else "SIN_CLAVE_EXACTA"
                for x in ventana if not x or x["estado_captura"] != "PPP_PUBLICADO_VERIFICADO"
            )
            ventanas_incompletas.append({"fecha": r["fecha"], "emisora": r["emisora"],
                                         "serie": r["serie"], "estados": dict(estados)})
    return {"contadores": dict(contadores), "desde_panel": min((r["fecha"] for r in panel), default=None),
            "hasta_panel": max((r["fecha"] for r in panel), default=None),
            "ventanas_incompletas": ventanas_incompletas,
            "limitacion": "Estados declarados no verifican evidencia, ajustes, fórmulas, ni autorización de redistribución."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historico", type=Path, required=True)
    p.add_argument("--panel", type=Path, required=True)
    args = p.parse_args()
    historico, sha_h = cargar(args.historico)
    panel, sha_p = cargar(args.panel)
    r = auditar(historico, panel)
    r.update(sha256_historico=sha_h, sha256_panel=sha_p)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
