import React, { useEffect, useId, useRef } from "react";
import { PrismiPulse } from "./PrismiPulse";
import { useDelayedFlag } from "../hooks/useDelayedFlag";

export function LoadingDialog({ active, title, detail, steps, onCancel }) {
  const visible = useDelayedFlag(active, 300);
  const dialogRef = useRef(null);
  const titleId = useId();

  useEffect(() => {
    if (!visible) return;
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => {
      if (dialog && dialog.open) dialog.close();
    };
  }, [visible]);

  if (!visible) return null;

  return (
    <dialog
      ref={dialogRef}
      className="geo-pulse-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <h2 id={titleId} className="geo-pulse-sr">{title}</h2>
      <PrismiPulse title={title} detail={detail} variant="modal" steps={steps} />
      <button className="button button-outline geo-pulse-cancel" onClick={onCancel} autoFocus>
        Cancelar consulta
      </button>
    </dialog>
  );
}
