import React, { useEffect, useRef, useState } from "react";
import { api } from "../../services/api.mjs";
import "./macro-ticker.css";

function fecha(valor) {
  if (!valor) return "Sin fecha";
  const [anio, mes, dia] = valor.split("-");
  return `${dia}/${mes}/${anio}`;
}

function valorIndicador(item) {
  if (item.valor == null) return "No disponible";
  const numero = new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: item.id === "usd_mxn" ? 4 : 2,
  }).format(item.valor);
  return item.id === "usd_mxn" ? `$${numero}` : `${numero}%`;
}

export function MacroTicker() {
  const [indicadores, setIndicadores] = useState([]);
  const [fallo, setFallo] = useState(false);
  const [seleccionado, setSeleccionado] = useState(null);
  const dialog = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let socket;
    let reintento;
    let espera = 1000;
    async function cargar() {
      try {
        const data = await api.getMacroIndicadores(controller.signal);
        if (!controller.signal.aborted) {
          setFallo(!data);
          if (data?.indicadores) setIndicadores(data.indicadores);
        }
      } catch {
        if (!controller.signal.aborted) setFallo(true);
      }
    }
    cargar();
    const url = import.meta.env.VITE_MACRO_WS_URL;
    function conectar() {
      if (!url || controller.signal.aborted) return;
      try {
        socket = new WebSocket(url);
        socket.onopen = () => {
          espera = 1000;
          cargar();
        };
        socket.onmessage = (event) => {
          try {
            if (JSON.parse(event.data).tipo === "macro_actualizada") cargar();
          } catch {
            // Se ignoran mensajes que no pertenezcan al protocolo de la cinta.
          }
        };
        socket.onclose = () => {
          if (!controller.signal.aborted) {
            reintento = window.setTimeout(conectar, espera);
            espera = Math.min(espera * 2, 60000);
          }
        };
      } catch {
        reintento = window.setTimeout(conectar, 60000);
      }
    }
    conectar();
    // Respaldo cuando el socket se cae o no está configurado.
    const intervalo = window.setInterval(cargar, 300000);
    return () => {
      controller.abort();
      window.clearInterval(intervalo);
      window.clearTimeout(reintento);
      socket?.close();
    };
  }, []);

  useEffect(() => {
    if (seleccionado && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [seleccionado]);

  return (
    <>
      <aside className="macro-bar" aria-label="Indicadores económicos oficiales">
        <span className="macro-bar-label">ECONOMÍA <span aria-hidden="true">●</span></span>
        <div className="macro-bar-items">
          {indicadores.map((item) => (
            <button key={item.id} className="macro-item" type="button" onClick={() => setSeleccionado(item)}>
              <strong>{item.simbolo}</strong>
              <span className="macro-value">{valorIndicador(item)}</span>
              <span className="macro-date">
                {fallo ? "Sin conexión · " : item.estado === "ultima_consulta_fallida" ? "Sin actualizar · " : ""}
                {fecha(item.fecha_dato)}
              </span>
            </button>
          ))}
          {!indicadores.length && <span className="macro-message">{fallo ? "Indicadores no disponibles" : "Consultando indicadores oficiales…"}</span>}
        </div>
        <span className="macro-source">Fuentes oficiales · No es tiempo real</span>
      </aside>
      {seleccionado && (
        <dialog className="macro-dialog" ref={dialog} onClose={() => setSeleccionado(null)} aria-labelledby="macro-title">
          <div className="macro-dialog-head">
            <div>
              <span className="macro-eyebrow">CONTEXTO ECONÓMICO</span>
              <h2 id="macro-title">{seleccionado.nombre}</h2>
            </div>
            <button type="button" className="macro-close" aria-label="Cerrar detalle" onClick={() => dialog.current?.close()}>×</button>
          </div>
          <p>{seleccionado.descripcion}</p>
          <div className="macro-detail-value">{valorIndicador(seleccionado)} <small>{seleccionado.unidad}</small></div>
          <p>Fecha del dato: <strong>{fecha(seleccionado.fecha_dato)}</strong></p>
          {(fallo || seleccionado.estado !== "disponible") && <p role="status">La consulta más reciente no está disponible; verifica la fecha del dato mostrado.</p>}
          <p>Fuente: <a href={seleccionado.url_fuente} target="_blank" rel="noreferrer">{seleccionado.fuente} ↗</a></p>
          <p className="macro-disclaimer">Información de contexto. Estos indicadores no necesariamente forman parte de las predicciones G2 y no son asesoría de inversión.</p>
        </dialog>
      )}
    </>
  );
}
