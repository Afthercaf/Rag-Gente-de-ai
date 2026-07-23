# Registro de bugs

## BUG 10 — El total usa el precio de un extra en lugar del de la pizza

### Problema

Después de confirmar un pedido y crear uno nuevo, el asistente puede mostrar el
precio de un extra como total de la pizza. Por ejemplo, para `Pizza Pepperoni`,
el total mostrado fue `$45.00`, aunque el precio de la pizza es `$115.00`.

### Resultado esperado

El total debe calcularse con el precio de la pizza seleccionada como base,
multiplicado por su cantidad. Solo se añaden extras que el cliente haya elegido
explícitamente.

| Pedido | Total esperado |
| --- | ---: |
| 1 Margarita | $105.00 |
| 1 Pepperoni | $115.00 |
| 2 Pepperoni | $230.00 |
| 1 Pastorera + Pepperoni extra | $265.00 |
| 1 Mexicana sin extras | $180.00 |

### Criterios de corrección

1. Buscar la pizza por nombre, solo dentro de la sección de pizzas del menú.
2. Obtener el precio asociado a esa pizza, no el primer precio disponible.
3. Multiplicar el precio base por la cantidad.
4. Sumar únicamente los extras seleccionados.
5. Limpiar el estado del pedido anterior antes de crear uno nuevo.

### Áreas a revisar

- `_compute_total()`
- `context_builder.py`
- `menu_formatter.py`
- `rag_service.py`

---

## BUG 11 — Se filtran instrucciones internas al responder preguntas del menú

### Problema

Ante la pregunta «¿tienes alguna que traiga refrescos?», el bot devolvió una
plantilla interna de formato de pedido, por ejemplo: «Si entregas un resumen de
pedido...», en lugar de contestar sobre el menú.

### Resultado esperado

Las instrucciones de sistema y las plantillas internas nunca deben aparecer en
las respuestas al cliente. Las preguntas informativas deben responderse con
datos del menú o una aclaración útil.

### Áreas a revisar

- Prompt del sistema y plantillas de respuesta.
- Separación entre instrucciones internas y contenido visible para el usuario.
- Manejo de preguntas informativas fuera del flujo de creación de pedidos.

---

## BUG 12 — Pedidos con múltiples pizzas se reducen a un único producto

### Problema

Un pedido de `1 Margarita, 3 Pepperoni y 2 Pastorera` se guarda como `Pizza
Margarita` con cantidad `6`, perdiendo las líneas de Pepperoni y Pastorera.

### Resultado esperado

El pedido debe conservar una línea por producto, con su cantidad, precio y
extras correspondientes. El resumen y el total deben sumar todas las líneas.

### Áreas a revisar

- Parser de intención y extracción de productos.
- Esquemas del pedido y estructura de líneas de orden.
- Contexto de conversación y persistencia de pedidos.
- Resumen, cálculo de total y envío a Telegram/Supabase.
