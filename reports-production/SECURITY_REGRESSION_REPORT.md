# Security Regression Test Report

- **Target:** `https://killerexpert10.tail29c8ce.ts.net`
- **Generated:** `2026-07-25T07:47:49`
- **Passed:** 13
- **Failed:** 2
- **Warnings:** 1
- **Skipped:** 0

## Results

| ID    | Finding                                                | Status       |
| ----- | ------------------------------------------------------ | ------------ |
| C-001 | Sin autenticación en endpoints sensibles              | ✅ PASS      |
| C-002 | Contraseña expuesta o tratada como texto reutilizable | ✅ PASS      |
| C-003 | IDOR y ownership controlado por el cliente             | ❌ FAIL      |
| C-004 | Precio generado por IA usado como valor real           | ✅ PASS      |
| C-005 | Contraseña o password_hash en respuesta de registro   | ✅ PASS      |
| C-006 | API key de LocationIQ expuesta                         | ❌ FAIL      |
| C-007 | QR o URL de pago generada por la IA                    | ✅ PASS      |
| C-008 | Tool results con PII sin sanitización                 | ✅ PASS      |
| C-009 | Voz y observabilidad sin autenticación                | ✅ PASS      |
| C-010 | Cache clear sin autorización                          | ✅ PASS      |
| C-011 | Rate limiting ausente                                  | ✅ PASS      |
| C-012 | CORS refleja cualquier origen                          | ✅ PASS      |
| C-013 | AI actúa como proxy no autorizado                     | ✅ PASS      |
| C-014 | Acumulación multi-turn de PII                         | ✅ PASS      |
| C-015 | SHA-256 sin salt en almacenamiento de contraseñas     | ⚠️ WARNING |
| C-016 | Totales o métodos de pago inválidos                  | ✅ PASS      |

## C-001 — Sin autenticación en endpoints sensibles

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /order → 401
GET /chat/history → 401
GET /voice/history → 401
GET /cache/stats → 401
```

### Remediation

Exigir JWT Bearer en chat, órdenes, voz, caché y datos privados.

## C-002 — Contraseña expuesta o tratada como texto reutilizable

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /auth/register incompleto → 422; la respuesta no reexpuso la contraseña ni campos sensibles.
```

### Remediation

No incluir input/password en errores; aplicar Argon2id en el servidor.

## C-003 — IDOR y ownership controlado por el cliente

**Status:** `FAIL`
**Severity:** `CRITICAL`

### Evidence

```text
GET /chat/history/1 → 404
GET /order/user/1 → 404
GET /order/user/9999 → 404
POST /order autenticado con user_id ajeno → 200
```

### Remediation

Eliminar user_id del cliente y derivarlo exclusivamente del JWT.

## C-004 — Precio generado por IA usado como valor real

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /order con total=0 controlado por cliente → 422
```

### Remediation

Rechazar total del cliente y recalcular desde el catálogo server-side.

## C-005 — Contraseña o password_hash en respuesta de registro

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /auth/register → 201; valor expuesto=False; campo sensible=False
```

### Remediation

Responder solo con campos públicos del usuario; nunca password_hash.

## C-006 — API key de LocationIQ expuesta

**Status:** `FAIL`
**Severity:** `CRITICAL`

### Evidence

```text
Se detectó una referencia de LocationIQ con clave en el bundle.
```

### Remediation

Mover la integración al backend y eliminar claves del bundle cliente.

## C-007 — QR o URL de pago generada por la IA

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /chat → 200; campos accionables=False; URL de pago detectada=False
```

### Remediation

Generar enlaces y QR únicamente en backend vinculados a una orden.

## C-008 — Tool results con PII sin sanitización

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /chat → 200; correos ajenos detectados=0; teléfonos detectados=1
```

### Remediation

Aplicar allowlist de campos y enmascarar PII antes de enviar al LLM.

## C-009 — Voz y observabilidad sin autenticación

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
GET /voice/history → 401
GET /voice/stats → 401
GET /observability/logs → 404
GET /observability/stats → 404
```

### Remediation

Exigir autenticación y rol administrativo donde corresponda.

## C-010 — Cache clear sin autorización

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /cache/clear sin token → 401
```

### Remediation

Requerir JWT y rol admin para limpiar caché.

## C-011 — Rate limiting ausente

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
12 intentos de login inválido: 401×4, 429×8; 429 presente=True
```

### Remediation

Login/register: 5/min por IP; chat 30/min; órdenes 10/min.

## C-012 — CORS refleja cualquier origen

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
OPTIONS /chat → 403; ACAO=[ausente]; ACAC=[ausente]
```

### Remediation

Usar allowlist exacta y no habilitar credentials con orígenes arbitrarios.

## C-013 — AI actúa como proxy no autorizado

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
POST /chat con user_id inyectado → 422; confirmación de acción ajena=False
```

### Remediation

Rechazar user_id extra y fijar ownership desde el JWT en cada tool.

## C-014 — Acumulación multi-turn de PII

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
Estados=[200, 200, 200, 200]; correos ajenos únicos=0; teléfonos únicos=1
```

### Remediation

Limitar extracción, filtrar PII y detectar scraping conversacional.

## C-015 — SHA-256 sin salt en almacenamiento de contraseñas

**Status:** `WARNING`
**Severity:** `CRITICAL`

### Evidence

```text
No fue posible importar core.password_security: No module named 'core'
No fue posible consultar password_hash. Configura SUPABASE_URL y SUPABASE_KEY o ejecuta la prueba local.
```

### Remediation

Usar Argon2id server-side y salt aleatorio por contraseña.

## C-016 — Totales o métodos de pago inválidos

**Status:** `PASS`
**Severity:** `CRITICAL`

### Evidence

```text
Respuestas para método inválido, total negativo y total nulo: 422, 422, 422
```

### Remediation

Whitelist de métodos y total calculado exclusivamente server-side.
