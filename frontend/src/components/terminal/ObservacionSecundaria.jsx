import React, { useEffect, useState } from "react";
import { request } from "../../services/api.mjs";

export function ObservacionSecundaria({ emisora, universo = null, habilitada = true }) {
  const [fecha, setFecha] = useState("");
  const [estado, setEstado] = useState({ data: null, error: "", loading: false });
  const [consulta, setConsulta] = useState(null);
  useEffect(() => { setConsulta(null); setEstado({ data: null, error: "", loading: false }); }, [emisora, universo]);
  useEffect(() => {
    if (!consulta || !habilitada) return undefined;
    const ctrl = new AbortController();
    setEstado({ data: null, error: "", loading: true });
    const params = new URLSearchParams({ emisora: consulta.emisora, fecha: consulta.fecha });
    if (consulta.universo) params.set("universo", consulta.universo);
    request(`/observaciones/yahoo?${params}`, { signal: ctrl.signal })
      .then((data) => {
        if (!ctrl.signal.aborted) setEstado({ data, error: data ? "" : "Sin observación disponible.", loading: false });
      })
      .catch((err) => {
        if (!ctrl.signal.aborted) setEstado({ data: null, error: err.message, loading: false });
      });
    return () => ctrl.abort();
  }, [consulta, habilitada]);
  return <section className="bk-card bk-card-pad" aria-label="Observación secundaria Yahoo Finance">
    <h3>Yahoo · observación secundaria ({emisora})</h3>
    <p>Cierre diario reportado, no PPP oficial BMV. No participa en las estadísticas anteriores ni en predicciones.</p>
    {!habilitada ? (
      <p role="status" className="bk-muted" style={{ fontSize: 13 }}>
        Compuerta en trámite de permiso (<code>evidencias/observaciones_yahoo/estado_permiso.json</code>).
        Los 35 símbolos <code>.MX</code> ya están verificados en MXN; la consulta se habilitará al aprobarse el permiso sin mezclarse con PPP BMV.
      </p>
    ) : (
      <>
        <form onSubmit={(e) => { e.preventDefault(); setConsulta({ emisora, fecha, universo }); }}>
          <label>Fecha de observación <input required type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
          <button type="submit" className="bk-btn bk-btn-ghost" disabled={estado.loading}>Consultar observación conservada</button>
        </form>
        {estado.error && <p role="status">{estado.error}</p>}
        {estado.data && <div>
          <p>{estado.data.simbolo} · {estado.data.fecha}: {estado.data.valor?.toLocaleString("es-MX")} {estado.data.moneda}</p>
          <p>{estado.data.advertencia}</p>
          <details><summary>Procedencia</summary><p>{estado.data.fuente} · {estado.data.timestamp_fuente_utc}</p>
            <code style={{ overflowWrap: "anywhere" }}>{estado.data.sha256_respuesta}</code></details>
        </div>}
      </>
    )}
  </section>;
}
