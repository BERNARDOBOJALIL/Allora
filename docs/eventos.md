## Eventos del Sistema

### `conversation.created`

**Publicado por:** Chat Service

Se emite cuando se crea una nueva conversación entre usuarios. Este evento informa a los demás servicios sobre la existencia de un nuevo canal de comunicación entre los participantes.

---

### `message.sent`

**Publicado por:** Chat Service

Se emite cuando un usuario envía un mensaje dentro de una conversación. Permite generar notificaciones para el receptor y actualizar el estado de actividad de la conversación.

---

### `messages.read`

**Publicado por:** Chat Service

Se emite cuando un usuario marca como leídos los mensajes de una conversación. Este evento permite actualizar el contador de mensajes pendientes y sincronizar el estado de lectura.

---

### `user.online`

**Publicado por:** Chat Service

Se emite cuando un usuario cambia su estado a “en línea”, indicando que actualmente se encuentra activo dentro de la plataforma.

---

### `user.offline`

**Publicado por:** Chat Service

Se emite cuando un usuario cambia su estado a “fuera de línea”, indicando que ya no se encuentra disponible en la plataforma.

---

### `match.created`

**Publicado por:** Match Service

Se emite cuando dos usuarios generan un match. Este evento permite habilitar conversaciones y enviar notificaciones relacionadas con la nueva conexión.

---

### `user.registered`

**Publicado por:** Auth Service

Se emite cuando un usuario completa exitosamente su registro dentro de la plataforma.

---

### `signal.sent`

**Publicado por:** Servicio de Interacción / Señales

Se emite cuando un usuario envía una señal de interés a otro usuario, permitiendo iniciar la interacción entre ambos perfiles.