export function cuerpoAlta({ nombre, email, password, rol, plan }, cognito) {
  return { nombre, email, rol, plan, ...(cognito ? {} : { password }) };
}

export function mensajeAlta(respuesta) {
  if (respuesta?.invitacion === "ACEPTADA_POR_COGNITO") {
    return "Cognito aceptó el envío de la invitación. La entrega y la verificación del correo aún no están confirmadas.";
  }
  if (respuesta?.invitacion === "ENVIO_NO_CONFIRMADO") {
    return "El perfil se creó, pero no se confirmó el envío. Revisa el estado antes de reintentar.";
  }
  return "Operación completada.";
}
