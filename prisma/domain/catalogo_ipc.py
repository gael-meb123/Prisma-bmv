"""Instantáneas de referencia, no autorización de mercado ni inferencia.

El catálogo NAFTRAC es provisional y corresponde a un solo corte; no afirma
pertenencia histórica ni composición oficial del índice. No se usa por la
ingesta ni por el backend de permisos o modelos.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent / "catalogos"
ESTADO_PROVISIONAL = "PROVISIONAL_NO_OFICIAL"
ESTADO_OFICIAL = "OFICIAL_VALIDADO"
ESTADO_MAPEO_PROPUESTO = "PROPUESTO_PENDIENTE_VERIFICACION"
ESTADO_MAPEO_CONFIRMADO = "CONFIRMADO_OFICIAL"
ALIAS_BLOQUEADOS_SIN_EVIDENCIA = frozenset({
    ("blackrock", "RA"),
    ("blackrock", "LIVEPOLC.1"),
})


@dataclass(frozen=True)
class ComponentePropuesto:
    emisora: str
    serie: str
    origen: str
    blackrock: str
    yahoo: str | None
    estado_composicion: str = ESTADO_PROVISIONAL
    estado_mapeo: str = "PROPUESTO_PENDIENTE_VERIFICACION"


@dataclass(frozen=True)
class CatalogoReferencia:
    version: str
    fecha_corte: date
    fecha_consulta: date
    fuente_nombre: str
    fuente_url: str
    componentes: tuple[ComponentePropuesto, ...]

    def en_corte(self, fecha: date) -> tuple[ComponentePropuesto, ...]:
        """No extender el corte a otras fechas ni suponer vigencias."""
        if fecha != self.fecha_corte:
            raise ValueError("Solo hay evidencia para la fecha de corte de esta instantánea.")
        return self.componentes

    def resolver(self, fuente: str, simbolo: str, fecha: date) -> ComponentePropuesto | None:
        """Resuelve alias exactos por fuente; los resultados siguen siendo propuestos."""
        self.en_corte(fecha)
        if fuente not in ("blackrock", "yahoo"):
            raise ValueError("Fuente de alias no admitida.")
        if not isinstance(simbolo, str) or not simbolo.strip():
            raise ValueError("El símbolo no puede estar vacío.")
        clave = simbolo.strip().upper()
        return next((c for c in self.componentes if getattr(c, fuente) == clave), None)

    def buscar_bmv(self, emisora: str, serie: str, fecha: date) -> ComponentePropuesto | None:
        """Busca el par BMV propuesto sin inferir la serie desde un ticker."""
        self.en_corte(fecha)
        if not isinstance(emisora, str) or not emisora.strip() or not isinstance(serie, str) or not serie.strip():
            raise ValueError("Emisora y serie son obligatorias.")
        clave = (emisora.strip().upper(), serie.strip().upper())
        return next((c for c in self.componentes if (c.emisora, c.serie) == clave), None)


def cargar_catalogo(ruta: Path) -> CatalogoReferencia:
    """Carga y valida una instantánea explícita; rechaza duplicados y ambigüedad."""
    raw = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if raw.get("estado_composicion") != ESTADO_PROVISIONAL:
        raise ValueError("Esta versión del lector solo admite composiciones provisionales.")
    version = raw.get("version")
    fuente = raw.get("fuente") or {}
    if not isinstance(version, str) or not version.strip() or not fuente.get("nombre") or not fuente.get("url"):
        raise ValueError("Faltan versión o procedencia del catálogo.")
    corte, consulta = date.fromisoformat(raw["fecha_corte"]), date.fromisoformat(raw["fecha_consulta"])
    if consulta < corte:
        raise ValueError("La consulta no puede anteceder al corte.")
    componentes = []
    pares, blackrock, yahoo = set(), set(), set()
    for fila in raw["componentes"]:
        campos = [fila.get(k) for k in ("emisora", "serie", "blackrock")]
        if any(not isinstance(v, str) or not v or v != v.strip().upper() for v in campos):
            raise ValueError("Emisora, serie y alias BlackRock deben estar normalizados.")
        if fila.get("origen") not in ("ACTUAL_15", "CANDIDATO_20"):
            raise ValueError("Origen desconocido.")
        alias_yahoo = fila.get("yahoo")
        if alias_yahoo is not None and (not isinstance(alias_yahoo, str) or not alias_yahoo
                                        or alias_yahoo != alias_yahoo.strip().upper()):
            raise ValueError("Alias Yahoo inválido.")
        par = (fila["emisora"], fila["serie"])
        if par in pares or fila["blackrock"] in blackrock or (alias_yahoo is not None and alias_yahoo in yahoo):
            raise ValueError("Par o alias duplicado para una misma fuente.")
        pares.add(par)
        blackrock.add(fila["blackrock"])
        if alias_yahoo is not None:
            yahoo.add(alias_yahoo)
        componentes.append(ComponentePropuesto(
            emisora=par[0], serie=par[1], origen=fila["origen"],
            blackrock=fila["blackrock"], yahoo=alias_yahoo,
        ))
    if not componentes:
        raise ValueError("La instantánea no puede estar vacía.")
    return CatalogoReferencia(version, corte, consulta, fuente["nombre"], fuente["url"], tuple(componentes))


def catalogo_naftrac_20261117() -> CatalogoReferencia:
    """Carga la versión explícita; no selecciona una versión vigente automáticamente."""
    return cargar_catalogo(DIRECTORIO / "naftrac_2026-11-17_v1.json")


@dataclass(frozen=True)
class AliasVersionado:
    fuente: str
    simbolo: str
    estado: str
    evidencia: str | None = None


@dataclass(frozen=True)
class ComponenteVersionado:
    instrumento_id: str
    emisora: str
    serie: str
    origen: str
    vigente_desde: date
    vigente_hasta: date | None
    estado_composicion: str
    estado_mapeo: str
    alias: tuple[AliasVersionado, ...]

    def activo_en(self, fecha: date) -> bool:
        """Intervalo semiabierto [vigente_desde, vigente_hasta)."""
        if fecha < self.vigente_desde:
            return False
        return self.vigente_hasta is None or fecha < self.vigente_hasta

    def alias_de(self, fuente: str, *, solo_confirmados: bool = True) -> str | None:
        for item in self.alias:
            if item.fuente == fuente and (not solo_confirmados or item.estado == ESTADO_MAPEO_CONFIRMADO):
                return item.simbolo
        return None


@dataclass(frozen=True)
class CatalogoVersionado:
    version: str
    fecha_publicacion: date
    fecha_consulta: date
    estado_composicion: str
    fuente_nombre: str
    fuente_url: str
    evidencia_s3_key: str | None
    sha256_evidencia: str | None
    componentes: tuple[ComponenteVersionado, ...]

    def en_fecha(self, fecha: date) -> tuple[ComponenteVersionado, ...]:
        """Devuelve componentes con vigencia explícita [desde, hasta); nunca infiere vigencias."""
        activos = tuple(c for c in self.componentes if c.activo_en(fecha))
        if not activos:
            raise ValueError(f"Sin evidencia de vigencia en el catálogo para {fecha.isoformat()}.")
        return activos

    def resolver_alias(self, fuente: str, simbolo: str, fecha: date, *, solo_confirmados: bool = True) -> ComponenteVersionado | None:
        if fuente not in ("bmv", "blackrock", "yahoo", "spdj"):
            raise ValueError("Fuente de alias no admitida.")
        if not isinstance(simbolo, str) or not simbolo.strip():
            raise ValueError("El símbolo no puede estar vacío.")
        clave = simbolo.strip().upper()
        for comp in self.en_fecha(fecha):
            if comp.alias_de(fuente, solo_confirmados=solo_confirmados) == clave:
                return comp
        return None

    def alias_confirmados(self, fuente: str, fecha: date) -> dict[str, str]:
        """Devuelve {emisora: simbolo} únicamente para alias confirmados oficialmente."""
        resultado = {}
        for comp in self.en_fecha(fecha):
            simbolo = comp.alias_de(fuente, solo_confirmados=True)
            if simbolo:
                resultado[comp.emisora] = simbolo
        return resultado


def _intervalos_solapan(a_ini: date, a_fin: date | None, b_ini: date, b_fin: date | None) -> bool:
    if a_fin is not None and a_fin <= b_ini:
        return False
    if b_fin is not None and b_fin <= a_ini:
        return False
    return True


def cargar_catalogo_versionado(raw: dict) -> CatalogoVersionado:
    """Valida un catálogo versionado (provisional u oficial) para S3 ``evidencias/catalogo_ipc/``.

    Exige hash SHA-256, clave de evidencia en S3, vigencias sin solapamientos y confirmación
    explícita de todos los mapeos/alias antes de admitir ``OFICIAL_VALIDADO``.
    """
    if not isinstance(raw, dict):
        raise ValueError("El catálogo versionado debe ser un objeto JSON.")
    estado_comp = raw.get("estado_composicion")
    if estado_comp not in (ESTADO_PROVISIONAL, ESTADO_OFICIAL):
        raise ValueError("estado_composicion inválido.")
    version = raw.get("version")
    fuente = raw.get("fuente") or {}
    if not isinstance(version, str) or not version.strip() or not fuente.get("nombre") or not fuente.get("url"):
        raise ValueError("Faltan versión o procedencia del catálogo.")
    fecha_pub = date.fromisoformat(raw["fecha_publicacion"])
    fecha_con = date.fromisoformat(raw["fecha_consulta"])
    if fecha_con < fecha_pub:
        raise ValueError("fecha_consulta no puede anteceder a fecha_publicacion.")
    evidencia_key = raw.get("evidencia_s3_key")
    sha_evidencia = raw.get("sha256_evidencia")
    if estado_comp == ESTADO_OFICIAL:
        if not isinstance(evidencia_key, str) or not evidencia_key.startswith("evidencias/catalogo_ipc/"):
            raise ValueError("Un catálogo OFICIAL_VALIDADO requiere evidencia_s3_key bajo evidencias/catalogo_ipc/.")
        if not isinstance(sha_evidencia, str) or not re.fullmatch(r"[0-9a-f]{64}", sha_evidencia):
            raise ValueError("Un catálogo OFICIAL_VALIDADO requiere sha256_evidencia válido de 64 hex.")

    filas = raw.get("componentes")
    if not isinstance(filas, list) or not filas:
        raise ValueError("El catálogo versionado no puede estar vacío.")

    componentes: list[ComponenteVersionado] = []
    por_par: dict[tuple[str, str], list[tuple[date, date | None]]] = {}
    por_alias: dict[tuple[str, str], list[tuple[date, date | None]]] = {}
    ids_vistos: set[tuple[str, date]] = set()

    for fila in filas:
        inst_id = fila.get("instrumento_id")
        emisora, serie = fila.get("emisora"), fila.get("serie")
        origen = fila.get("origen")
        if (not isinstance(inst_id, str) or not inst_id.strip()
                or any(not isinstance(x, str) or not x or x != x.strip().upper() for x in (emisora, serie))):
            raise ValueError("instrumento_id, emisora y serie deben estar normalizados.")
        if origen not in ("ACTUAL_15", "CANDIDATO_20", "IPC_OFICIAL"):
            raise ValueError(f"Origen desconocido: {origen!r}")
        v_desde = date.fromisoformat(fila["vigente_desde"])
        v_hasta = date.fromisoformat(fila["vigente_hasta"]) if fila.get("vigente_hasta") is not None else None
        if v_hasta is not None and v_hasta <= v_desde:
            raise ValueError("vigente_hasta debe ser posterior a vigente_desde (intervalo semiabierto).")
        if (inst_id, v_desde) in ids_vistos:
            raise ValueError("Instrumento duplicado en la misma fecha de vigencia.")
        ids_vistos.add((inst_id, v_desde))

        estado_mapeo = fila.get("estado_mapeo")
        if estado_mapeo not in (ESTADO_MAPEO_PROPUESTO, ESTADO_MAPEO_CONFIRMADO):
            raise ValueError(f"estado_mapeo inválido: {estado_mapeo!r}")
        if estado_comp == ESTADO_OFICIAL and estado_mapeo != ESTADO_MAPEO_CONFIRMADO:
            raise ValueError(f"Un catálogo OFICIAL_VALIDADO no admite mapeos sin confirmar ({emisora} {serie}).")

        par = (emisora, serie)
        for prev_ini, prev_fin in por_par.get(par, []):
            if _intervalos_solapan(prev_ini, prev_fin, v_desde, v_hasta):
                raise ValueError(f"Vigencia solapada para {emisora} {serie}.")
        por_par.setdefault(par, []).append((v_desde, v_hasta))

        alias_lista = []
        for al in fila.get("alias") or []:
            f_al = al.get("fuente")
            sym = al.get("simbolo")
            est_al = al.get("estado")
            ev_al = al.get("evidencia")
            if f_al not in ("bmv", "blackrock", "yahoo", "spdj"):
                raise ValueError(f"Fuente de alias inválida: {f_al!r}")
            if not isinstance(sym, str) or not sym or sym != sym.strip().upper():
                raise ValueError(f"Símbolo de alias inválido: {sym!r}")
            if est_al not in (ESTADO_MAPEO_PROPUESTO, ESTADO_MAPEO_CONFIRMADO):
                raise ValueError(f"Estado de alias inválido: {est_al!r}")
            if est_al == ESTADO_MAPEO_CONFIRMADO and (not isinstance(ev_al, str) or not ev_al.strip()):
                raise ValueError(f"Alias confirmado sin evidencia ({f_al}:{sym}).")
            if estado_comp == ESTADO_OFICIAL and (f_al, sym) in ALIAS_BLOQUEADOS_SIN_EVIDENCIA and est_al != ESTADO_MAPEO_CONFIRMADO:
                raise ValueError(f"Alias sensible pendiente de evidencia oficial: {f_al}:{sym}.")
            for prev_ini, prev_fin in por_alias.get((f_al, sym), []):
                if _intervalos_solapan(prev_ini, prev_fin, v_desde, v_hasta):
                    raise ValueError(f"Alias solapado para {f_al}:{sym}.")
            por_alias.setdefault((f_al, sym), []).append((v_desde, v_hasta))
            alias_lista.append(AliasVersionado(fuente=f_al, simbolo=sym, estado=est_al, evidencia=ev_al))

        componentes.append(ComponenteVersionado(
            instrumento_id=inst_id.strip(),
            emisora=emisora,
            serie=serie,
            origen=origen,
            vigente_desde=v_desde,
            vigente_hasta=v_hasta,
            estado_composicion=estado_comp,
            estado_mapeo=estado_mapeo,
            alias=tuple(alias_lista),
        ))

    return CatalogoVersionado(
        version=version.strip(),
        fecha_publicacion=fecha_pub,
        fecha_consulta=fecha_con,
        estado_composicion=estado_comp,
        fuente_nombre=fuente["nombre"],
        fuente_url=fuente["url"],
        evidencia_s3_key=evidencia_key,
        sha256_evidencia=sha_evidencia,
        componentes=tuple(componentes),
    )


def convertir_provisional_a_versionado(catalogo: CatalogoReferencia, *, fecha_consulta_iso: str | None = None) -> dict:
    """Empaqueta una instantánea provisional de un solo corte (vigencia [corte, corte+1 día))."""
    from datetime import timedelta

    fin_exclusivo = (catalogo.fecha_corte + timedelta(days=1)).isoformat()
    filas = []
    for c in catalogo.componentes:
        alias = [{"fuente": "blackrock", "simbolo": c.blackrock, "estado": ESTADO_MAPEO_PROPUESTO, "evidencia": None}]
        if c.yahoo:
            alias.append({"fuente": "yahoo", "simbolo": c.yahoo, "estado": ESTADO_MAPEO_PROPUESTO, "evidencia": None})
        filas.append({
            "instrumento_id": f"BMV:{c.emisora}:{c.serie}",
            "emisora": c.emisora,
            "serie": c.serie,
            "origen": c.origen,
            "vigente_desde": catalogo.fecha_corte.isoformat(),
            "vigente_hasta": fin_exclusivo,
            "estado_mapeo": ESTADO_MAPEO_PROPUESTO,
            "alias": alias,
        })
    return {
        "version": catalogo.version,
        "fecha_publicacion": catalogo.fecha_corte.isoformat(),
        "fecha_consulta": fecha_consulta_iso or catalogo.fecha_consulta.isoformat(),
        "estado_composicion": ESTADO_PROVISIONAL,
        "fuente": {"nombre": catalogo.fuente_nombre, "url": catalogo.fuente_url},
        "evidencia_s3_key": None,
        "sha256_evidencia": None,
        "componentes": filas,
    }
