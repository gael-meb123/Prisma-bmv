"""Cuentas cifradas, contraseñas, bloqueo, cuotas y pasarela sandbox."""

import hashlib
import json
from datetime import date

import pytest
from cryptography.fernet import Fernet

from prisma.plans import ENTERPRISE, EXPLORER, PROFESSIONAL, tiene_acceso
from prisma.security.crypto import (AlmacenCifrado, ErrorConfiguracionSeguridad, hash_password,
                                    obtener_fernet, requiere_rehash, verificar_password)
from prisma.services.auth import MSG_CREDENCIALES, ServicioUsuarios
from prisma.services.billing import PasarelaSandbox, luhn_valido, validar_datos

PWD = "ClaveSegura2026"


@pytest.fixture
def fernet():
    return Fernet(Fernet.generate_key())


@pytest.fixture
def svc(tmp_path, fernet):
    return ServicioUsuarios(AlmacenCifrado(tmp_path / "u.enc", fernet), 1000)


def test_pbkdf2_verifica_y_detecta_iteraciones_bajas():
    h = hash_password(PWD, 1000)
    assert h.startswith("pbkdf2_sha256$1000$")
    assert verificar_password(PWD, h) and not verificar_password("otra", h)
    assert requiere_rehash(h, 600_000) and not requiere_rehash(h, 1000)


def test_almacen_cifrado_no_expone_datos_y_detecta_alteracion(tmp_path, fernet, svc):
    svc.registrar("Ana", "ana@fondo.mx", PWD)
    crudo = (tmp_path / "u.enc").read_bytes()
    assert b"ana@fondo.mx" not in crudo and b"pbkdf2" not in crudo
    (tmp_path / "u.enc").write_bytes(crudo[:-5] + b"XXXXX")
    with pytest.raises(ErrorConfiguracionSeguridad):
        svc.obtener("ana@fondo.mx")


def test_produccion_exige_llave_maestra(tmp_path):
    with pytest.raises(ErrorConfiguracionSeguridad):
        obtener_fernet("", tmp_path, es_produccion=True)
    obtener_fernet("", tmp_path, es_produccion=False)
    assert (tmp_path / "llave_maestra.key").exists()


def test_registro_siempre_inicia_en_explorer(svc):
    ok, _ = svc.registrar("Ana", "Ana@Fondo.mx", PWD)
    assert ok and svc.obtener("ana@fondo.mx")["plan"] == EXPLORER
    assert not svc.registrar("Ana", "ana@fondo.mx", PWD)[0]
    assert not svc.registrar("B", "b@x.mx", "corta1")[0]
    assert not svc.registrar("B", "b@x.mx", "sololetraslargas")[0]


def test_mensaje_generico_y_bloqueo_tras_5_intentos(svc):
    svc.registrar("Ana", "ana@fondo.mx", PWD)
    assert svc.autenticar("nadie@x.mx", PWD)[2] == MSG_CREDENCIALES
    for _ in range(5):
        assert svc.autenticar("ana@fondo.mx", "mala1234567")[2] == MSG_CREDENCIALES
    ok, _, msg = svc.autenticar("ana@fondo.mx", PWD)
    assert not ok and "bloqueada" in msg


def test_migracion_de_hash_heredado(tmp_path, svc):
    sal = "abc123"
    legado = {"viejo@x.mx": {"nombre": "Viejo", "password_hash": hashlib.sha256((sal + PWD).encode()).hexdigest(),
                             "salt": sal, "plan": "professional"}}
    ruta = tmp_path / "usuarios.json"
    ruta.write_text(json.dumps(legado))
    assert svc.importar_legado(ruta) == 1
    ok, u, _ = svc.autenticar("viejo@x.mx", PWD)
    assert ok and u["plan"] == PROFESSIONAL
    interno = svc._cargar()["viejo@x.mx"]
    assert interno["password_hash"].startswith("pbkdf2_sha256$") and "legacy_sha256" not in interno


def test_cuota_diaria_de_prismi(svc):
    svc.registrar("Ana", "ana@fondo.mx", PWD)
    resultados = [svc.consumir_cuota_prismi("ana@fondo.mx", 2, "2026-11-05") for _ in range(3)]
    assert resultados == [(True, 1), (True, 0), (False, 0)]
    assert svc.consumir_cuota_prismi("ana@fondo.mx", 2, "2026-11-06") == (True, 1)


def test_matriz_de_derechos():
    assert not tiene_acceso(EXPLORER, "panel_g2")
    assert tiene_acceso(PROFESSIONAL, "panel_g2") and not tiene_acceso(PROFESSIONAL, "lakehouse_athena")
    assert all(tiene_acceso(ENTERPRISE, d) for d in ("panel_g2", "lakehouse_athena", "auditoria_sha256_forense"))
    with pytest.raises(KeyError):
        tiene_acceso(ENTERPRISE, "inexistente")


# --- Pasarela -----------------------------------------------------------------
def test_luhn_y_validaciones():
    assert luhn_valido("4242424242424242") and not luhn_valido("4242424242424241")
    hoy = date(2026, 11, 5)
    assert validar_datos("4242424242424242", "10/26", "123", "Ana", hoy) == "La tarjeta está vencida."
    assert validar_datos("4242424242424242", "11/26", "123", "Ana", hoy) is None
    assert validar_datos("4242424242424242", "13/27", "123", "Ana", hoy).startswith("Use el formato")


def test_cobro_aprobado_y_sin_datos_sensibles(tmp_path, fernet):
    libro = AlmacenCifrado(tmp_path / "p.enc", fernet)
    pas = PasarelaSandbox(libro)
    tx, _ = pas.cobrar("a@b.mx", PROFESSIONAL, "4242 4242 4242 4242", "12/30", "123", "Ana")
    assert tx.estado == "APROBADA" and tx.monto_usd == 49 and tx.ultimos4 == "4242"
    texto = json.dumps(libro.cargar())
    assert "4242424242424242" not in texto and '"123"' not in texto


def test_rechazos_y_tarjetas_reales_bloqueadas(tmp_path, fernet):
    pas = PasarelaSandbox(AlmacenCifrado(tmp_path / "p.enc", fernet))
    tx, msg = pas.cobrar("a@b.mx", ENTERPRISE, "4000000000000002", "12/30", "123", "Ana")
    assert tx.estado == "RECHAZADA" and tx.motivo == "TARJETA_DECLINADA"
    tx, msg = pas.cobrar("a@b.mx", ENTERPRISE, "4111111111111111", "12/30", "123", "Ana")
    assert tx.motivo == "TARJETA_NO_ES_DE_PRUEBA"
    assert pas.cobrar("a@b.mx", EXPLORER, "4242424242424242", "12/30", "123", "Ana")[0] is None
