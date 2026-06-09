# Persistencia del Historial de Conversación

El sistema ahora guarda automáticamente el historial de conversación de cada usuario en archivos JSON.

## Características

- ✅ **Persistencia Automática**: Cada mensaje se guarda en disco automáticamente
- ✅ **Carga al Iniciar**: Al comenzar una sesión, se carga el historial previo del usuario
- ✅ **Gestión por Usuario**: Cada usuario tiene su propio archivo JSON de historial
- ✅ **Límite de Mensajes**: Se mantienen los últimos 20 mensajes por usuario
- ✅ **Timestamps**: Cada mensaje incluye marca de tiempo ISO

## Estructura de Archivos

```
data/
└── histories/
    ├── user_1.json
    ├── user_2.json
    └── user_N.json
```

## Formato del Archivo de Historial

Cada archivo JSON tiene esta estructura:

```json
{
  "user_id": 1,
  "messages": [
    {
      "user": "Hola, quiero una pizza",
      "assistant": "¡Bienvenido! ¿Qué tipo de pizza te gustaría?",
      "timestamp": "2026-06-09T14:30:45.123456"
    },
    {
      "user": "Una margherita grande",
      "assistant": "Perfecto, registré tu orden...",
      "timestamp": "2026-06-09T14:31:12.654321"
    }
  ],
  "last_updated": "2026-06-09T14:31:12.654321"
}
```

## API Endpoints

### Enviar Mensaje (con guardar automático)
```bash
POST /chat
Content-Type: application/json

{
  "user_id": 1,
  "message": "Quiero una pizza",
  "use_cache": true
}
```

### Obtener Historial de Usuario
```bash
GET /chat/history/{user_id}

# Respuesta:
{
  "user_id": 1,
  "messages_count": 5,
  "history": [...]
}
```

### Limpiar Historial de Usuario
```bash
DELETE /chat/history/{user_id}

# Respuesta:
{
  "status": "ok",
  "message": "✅ Historial del usuario 1 eliminado"
}
```

## Funciones del Servicio

### `services/history_service.py`

- `load_history(user_id)` - Carga el historial del usuario
- `save_history(user_id, history)` - Guarda historial a disco
- `append_message(user_id, user_msg, assistant_msg)` - Agrega y persiste un mensaje
- `clear_history(user_id)` - Elimina el historial del usuario
- `get_all_user_ids()` - Lista todos los IDs de usuario con historial

### `services/session_service.py`

- `get_user_session(user_id)` - Obtiene/crea sesión (carga historial persistido)
- `append_to_history(session, user_id, user_msg, assistant_msg)` - Agrega a memoria y persiste
- `build_history_text(session)` - Formatea historial para el prompt
- `build_enriched_query(session, query)` - Enriquece búsqueda con contexto reciente

## Integración en el Código

El router de chat (`routers/chat.py`) automáticamente:

1. Carga el historial del usuario al iniciar sesión
2. Guarda cada mensaje en disco después de obtener respuesta
3. Usa el historial para enriquecer búsquedas RAG
4. Limita el historial a los últimos 20 mensajes

## Ejemplo de Uso

```python
from services.history_service import load_history, append_message

# Cargar historial
history = load_history(user_id=1)
print(f"Usuario 1 tiene {len(history)} mensajes")

# Agregar nuevo mensaje (se guarda automáticamente)
append_message(
    user_id=1,
    user_msg="Quiero una pizza pepperoni",
    assistant_msg="Excelente, una pepperoni grande..."
)
```

## Notas Importantes

- La carpeta `data/` está en `.gitignore` (no se sube a repositorio)
- Los archivos JSON se guardan con encoding UTF-8
- Se mantiene una copia en memoria para la sesión actual
- Los timestamps en ISO son compatibles con todas las zonas horarias
