import React, { createContext, useContext, useState } from "react";
import { planById } from "../plans.mjs";

const AccountContext = createContext(null);

export function AccountProvider({ children }) {
  // Plan por defecto: explorer (gratuito)
  const [role, setRole] = useState("explorer");
  const [user, setUser] = useState({
    email: "analista.demo@prismabmv.com",
    name: "Analista Cuantitativo"
  });

  function switchPlan(newRole) {
    setRole(newRole);
  }

  function leave() {
    setUser(null);
    setRole("explorer");
  }

  function enter(email, name, selectedRole = "explorer") {
    setUser({ email, name: name || "Analista" });
    setRole(selectedRole);
  }

  const value = {
    user,
    role,
    ready: true,
    authReady: true,
    plan: planById(role),
    switchPlan,
    enter,
    leave
  };

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error("useAccount debe usarse dentro de AccountProvider");
  return ctx;
}
