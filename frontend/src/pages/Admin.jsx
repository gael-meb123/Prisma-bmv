import React, { useState, useEffect, useCallback } from "react";
import { Users, UserPlus, Shield, ChevronDown, ChevronUp, X, Check, AlertTriangle } from "lucide-react";
import { Header } from "../components/Header";
import { Button, Notice } from "../components/UI";
import { useAccount } from "../hooks/useAccount";
import { api } from "../services/api.mjs";
import { PLANS } from "../plans.mjs";

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------
export function Admin() {
  const account = useAccount();
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // --- Formulario de alta ---
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ nombre: "", email: "", password: "", rol: "user", plan: "explorer" });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  // --- Edición inline ---
  const [editId, setEditId] = useState(null);
  const [editData, setEditData] = useState({});
  const [editLoading, setEditLoading] = useState(false);

  const cargar = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.admin.listarUsuarios();
      setUsuarios(data || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar los usuarios.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  // --- Redirección si no es admin ---
  if (account.ready && account.userRole !== "admin") {
    return (
      <>
        <Header />
        <main id="main-content" className="information-page container" style={{ maxWidth: "600px", margin: "60px auto", padding: "0 20px", textAlign: "center" }}>
          <AlertTriangle size={48} style={{ color: "#f59e0b", marginBottom: "16px" }} />
          <h1 style={{ color: "var(--navy)", fontSize: "24px" }}>Acceso Restringido</h1>
          <p style={{ color: "var(--muted)", fontSize: "14px", marginTop: "8px" }}>
            Esta sección es exclusiva para administradores.
          </p>
          <a href="#/sistema" className="button button-primary" style={{ marginTop: "24px", display: "inline-flex", padding: "10px 24px" }}>
            Volver a la Terminal
          </a>
        </main>
      </>
    );
  }

  // --- Crear usuario ---
  async function handleCrear(e) {
    e.preventDefault();
    setFormError("");
    setFormLoading(true);
    try {
      await api.admin.crearUsuario({
        nombre: form.nombre.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        rol: form.rol,
        plan: form.plan,
      });
      setForm({ nombre: "", email: "", password: "", rol: "user", plan: "explorer" });
      setShowForm(false);
      await cargar();
    } catch (err) {
      setFormError(err.message || "No se pudo crear el usuario.");
    } finally {
      setFormLoading(false);
    }
  }

  // --- Guardar edición ---
  async function handleGuardar(uid) {
    setEditLoading(true);
    try {
      const cambios = {};
      const original = usuarios.find((u) => u.id === uid);
      if (editData.rol !== original.rol) cambios.rol = editData.rol;
      if (editData.plan !== original.plan) cambios.plan = editData.plan;
      if (Object.keys(cambios).length === 0) {
        setEditId(null);
        return;
      }
      await api.admin.actualizarUsuario(uid, cambios);
      setEditId(null);
      await cargar();
      // Si el admin se cambió su propio plan, refrescar su perfil
      if (uid === account.profile?.id) await account.refreshProfile();
    } catch (err) {
      alert(err.message || "No se pudo actualizar.");
    } finally {
      setEditLoading(false);
    }
  }

  function startEdit(u) {
    setEditId(u.id);
    setEditData({ rol: u.rol, plan: u.plan });
  }

  return (
    <>
      <Header />

      <main id="main-content" className="information-page container" style={{ maxWidth: "960px", margin: "40px auto", padding: "0 20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <span className="eyebrow">ADMINISTRACIÓN</span>
            <h1 style={{ color: "var(--navy)", fontSize: "28px", margin: "4px 0" }}>
              <Users size={24} style={{ verticalAlign: "middle", marginRight: "8px" }} />
              Gestión de Usuarios
            </h1>
          </div>
          <Button variant="primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? <><X size={16} /> Cancelar</> : <><UserPlus size={16} /> Nuevo Usuario</>}
          </Button>
        </div>

        {/* ---- Formulario de alta ---- */}
        {showForm && (
          <div style={{ margin: "24px 0", padding: "24px", background: "#f8fafc", border: "1px solid var(--line)", borderRadius: "12px" }}>
            <h3 style={{ color: "var(--navy)", fontSize: "16px", margin: "0 0 16px" }}>Dar de alta un usuario</h3>
            {formError && (
              <div style={{ padding: "8px 12px", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "8px", fontSize: "13px", color: "#b91c1c", marginBottom: "12px" }}>
                {formError}
              </div>
            )}
            <form onSubmit={handleCrear} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <input
                type="text" required placeholder="Nombre"
                value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                style={inputStyle}
              />
              <input
                type="email" required placeholder="Correo"
                value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                style={inputStyle}
              />
              <input
                type="password" required minLength={8} placeholder="Contraseña (mín. 8)"
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                style={inputStyle}
              />
              <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })} style={inputStyle}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
              <select value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })} style={inputStyle}>
                {PLANS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <Button variant="primary" type="submit" disabled={formLoading} style={{ justifyContent: "center" }}>
                {formLoading ? "Creando…" : "Crear Usuario"}
              </Button>
            </form>
          </div>
        )}

        {/* ---- Error / carga ---- */}
        {error && <Notice tone="warning" style={{ marginTop: "16px" }}>{error}</Notice>}
        {loading && <p style={{ color: "var(--muted)", marginTop: "24px" }}>Cargando usuarios…</p>}

        {/* ---- Tabla de usuarios ---- */}
        {!loading && usuarios.length > 0 && (
          <div style={{ marginTop: "24px", overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--line)", textAlign: "left" }}>
                  <th style={thStyle}>Nombre</th>
                  <th style={thStyle}>Correo</th>
                  <th style={thStyle}>Rol</th>
                  <th style={thStyle}>Plan</th>
                  <th style={thStyle}>Creado</th>
                  <th style={{ ...thStyle, textAlign: "center" }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => {
                  const isEditing = editId === u.id;
                  const isMe = u.id === account.profile?.id;
                  return (
                    <tr key={u.id} style={{ borderBottom: "1px solid var(--line)", background: isMe ? "#f0fdfa" : "transparent" }}>
                      <td style={tdStyle}>
                        {u.nombre || "—"}
                        {isMe && <span style={{ fontSize: "11px", color: "#079baa", marginLeft: "6px" }}>(tú)</span>}
                      </td>
                      <td style={tdStyle}>{u.email}</td>
                      <td style={tdStyle}>
                        {isEditing ? (
                          <select
                            value={editData.rol}
                            onChange={(e) => setEditData({ ...editData, rol: e.target.value })}
                            style={{ ...inputStyle, padding: "4px 8px", fontSize: "12px" }}
                            disabled={isMe}
                            title={isMe ? "No puedes quitarte tu propio rol de admin" : ""}
                          >
                            <option value="user">user</option>
                            <option value="admin">admin</option>
                          </select>
                        ) : (
                          <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                            {u.rol === "admin" && <Shield size={14} style={{ color: "#079baa" }} />}
                            {u.rol}
                          </span>
                        )}
                      </td>
                      <td style={tdStyle}>
                        {isEditing ? (
                          <select
                            value={editData.plan}
                            onChange={(e) => setEditData({ ...editData, plan: e.target.value })}
                            style={{ ...inputStyle, padding: "4px 8px", fontSize: "12px" }}
                          >
                            {PLANS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                          </select>
                        ) : (
                          planLabel(u.plan)
                        )}
                      </td>
                      <td style={tdStyle}>{formatDate(u.creado_en)}</td>
                      <td style={{ ...tdStyle, textAlign: "center" }}>
                        {isEditing ? (
                          <span style={{ display: "inline-flex", gap: "6px" }}>
                            <button onClick={() => handleGuardar(u.id)} disabled={editLoading} style={actionBtn} title="Guardar">
                              <Check size={16} style={{ color: "#10b981" }} />
                            </button>
                            <button onClick={() => setEditId(null)} style={actionBtn} title="Cancelar">
                              <X size={16} style={{ color: "#ef4444" }} />
                            </button>
                          </span>
                        ) : (
                          <button onClick={() => startEdit(u)} style={actionBtn} title="Editar rol y plan">
                            ✏️
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && usuarios.length === 0 && !error && (
          <p style={{ color: "var(--muted)", marginTop: "24px" }}>No hay usuarios registrados.</p>
        )}
      </main>
    </>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function planLabel(id) {
  const p = PLANS.find((x) => x.id === id);
  return p ? p.name : id;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("es-MX", { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}

const inputStyle = {
  padding: "8px 12px",
  borderRadius: "8px",
  border: "1px solid var(--line)",
  fontSize: "13px",
  background: "#ffffff",
  width: "100%",
};

const thStyle = {
  padding: "10px 12px",
  fontSize: "11px",
  fontWeight: "700",
  color: "var(--muted)",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const tdStyle = {
  padding: "10px 12px",
  color: "var(--navy)",
};

const actionBtn = {
  background: "none",
  border: "none",
  cursor: "pointer",
  padding: "4px",
  borderRadius: "4px",
};
