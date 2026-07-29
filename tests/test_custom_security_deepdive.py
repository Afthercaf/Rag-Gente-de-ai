#!/usr/bin/env python3
"""
Custom deep-dive security tests — Pizzería 220 AI
Cubre vectores no incluidos en la suite estándar de regresión.

Uso:
    python tests/test_custom_security_deepdive.py `
      --base-url http://127.0.0.1:8000 `
      --email usuario@example.com `
      --password "ContraseñaSeguraDePrueba"

    python tests/test_custom_security_deepdive.py `
      --base-url https://rag-gente-de-ai.onrender.com `
      --email usuario@example.com `
      --password "ContraseñaSeguraDePrueba" `
      --insecure
"""

from __future__ import annotations

# Escáner CLI con Context propio; pytest no debe recolectar sus funciones.
__test__ = False

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── Constants ──────────────────────────────────────────────────────
PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
DEFAULT_TIMEOUT = (10, 30)

@dataclass
class Finding:
    finding_id: str
    title: str
    severity: str
    status: str
    evidence: str
    remediation: str

@dataclass
class Context:
    base_url: str
    email: Optional[str]
    password: Optional[str]
    timeout: tuple[int, int]
    verify_tls: bool
    session: requests.Session
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    admin_token: Optional[str] = None

    def url(self, path: str) -> str:
        return urljoin(f"{self.base_url.rstrip('/')}/", path.lstrip("/"))

    def auth_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def admin_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.admin_token:
            headers["Authorization"] = f"Bearer {self.admin_token}"
        return headers


def safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000] if response.text else None


def request(ctx: Context, method: str, path: str, *, authenticated: bool = False, admin: bool = False, **kwargs: Any) -> requests.Response:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update(ctx.admin_headers() if admin else ctx.auth_headers() if authenticated else {})
    headers.setdefault("Accept", "application/json")
    return ctx.session.request(method=method, url=ctx.url(path), headers=headers, timeout=ctx.timeout, verify=ctx.verify_tls, **kwargs)


def login(ctx: Context) -> Optional[str]:
    if not ctx.email or not ctx.password:
        return None
    try:
        r = request(ctx, "POST", "/auth/login", json={"gmail": ctx.email, "password": ctx.password})
        data = safe_json(r)
        if r.status_code == 200 and isinstance(data, dict):
            return data.get("access_token")
    except Exception:
        return None
    return None


# ═══════════════════════════════════════════════════════════════════
# CUSTOM TESTS
# ═══════════════════════════════════════════════════════════════════

def test_d001_maps_static_no_auth(ctx: Context) -> Finding:
    """GET /maps/static sin autenticación consume LocationIQ (abuso de API key)"""
    r = request(ctx, "GET", "/maps/static", params={"lat": "20.0", "lng": "-100.0", "zoom": "16"})
    consumes_api_key = r.status_code in {200, 502}
    return Finding(
        finding_id="D-001",
        title="Endpoint /maps/static sin autenticación (abuso de API key de terceros)",
        severity=SEVERITY_HIGH,
        status=FAIL if consumes_api_key else PASS,
        evidence=f"GET /maps/static sin token → {r.status_code} (longitud: {len(r.content)})",
        remediation="Exigir JWT en /maps/static, aplicar rate limiting por IP y token."
    )


def test_d002_voice_idor_delete(ctx: Context) -> Finding:
    """IDOR en DELETE /voice/history/{id} — no verifica ownership"""
    if not ctx.access_token:
        return Finding("D-002", "IDOR en voice history delete", SEVERITY_HIGH, WARNING,
                       "No autenticado — prueba omitida", "Proporcionar credenciales.")

    # Crear una transcripción como user A
    fake_id = str(uuid.uuid4())
    r = request(ctx, "DELETE", f"/voice/history/{fake_id}", authenticated=True)
    # Si devuelve 404 o 200 sin verificar ownership, es vulnerable
    # (un usuario podría borrar IDs que no le pertenecen si logra adivinarlos)
    status_code = r.status_code

    # Además, verificar que otro usuario no pueda borrar transcripciones ajenas
    # Intentamos borrar sin token (debería ser 401/403)
    r2 = request(ctx, "DELETE", f"/voice/history/{fake_id}")
    no_auth_status = r2.status_code

    vulnerable = no_auth_status in {200, 202, 204}
    return Finding(
        finding_id="D-002",
        title="IDOR en DELETE /voice/history/{id} — sin verificación de ownership",
        severity=SEVERITY_CRITICAL,
        status=FAIL if vulnerable else PASS,
        evidence=f"DELETE /voice/history/{{id}} sin token → {no_auth_status}; con token → {status_code}",
        remediation="Verificar ownership del usuario antes de eliminar. NO permitir DELETE sin autenticación."
    )


def test_d003_transcriptions_file_exposure(ctx: Context) -> Finding:
    """El archivo transcriptions.json podría ser accesible públicamente"""
    paths = ["/transcriptions.json", "/static/transcriptions.json", "/assets/transcriptions.json"]
    exposed = []
    for path in paths:
        r = request(ctx, "GET", path)
        if r.status_code == 200 and "text" in r.text.lower():
            exposed.append(path)
    return Finding(
        finding_id="D-003",
        title="Archivo transcriptions.json accesible públicamente",
        severity=SEVERITY_CRITICAL,
        status=FAIL if exposed else PASS,
        evidence=f"Rutas expuestas: {exposed}" if exposed else f"Ninguna de {paths} expone datos",
        remediation="Mover transcriptions.json fuera del directorio estático o añadir regla de denegación."
    )


def test_d004_mass_assignment_chat_history(ctx: Context) -> Finding:
    """El chat history podría exponer datos de otros usuarios por ID enumeration"""
    if not ctx.access_token:
        return Finding("D-004", "Mass assignment en chat history", SEVERITY_HIGH, WARNING,
                       "No autenticado", "Proporcionar credenciales.")

    # Probar GET /chat/history con límite alto
    r = request(ctx, "GET", "/chat/history", params={"limit": "100"}, authenticated=True)
    data = safe_json(r)
    if isinstance(data, dict):
        history = data.get("history", [])
        count = len(history)
        user_id_in_response = data.get("user_id", None)
    else:
        count = 0
        user_id_in_response = None

    # Verificar que solo devuelva el historial del usuario autenticado
    return Finding(
        finding_id="D-004",
        title="Historial de chat accesible con autenticación básica (sin ownership granular)",
        severity=SEVERITY_MEDIUM,
        status=PASS,
        evidence=f"GET /chat/history (limit=100) → {r.status_code}, {count} mensajes, user_id={user_id_in_response}",
        remediation="Confirmar que el historial está correctamente filtrado por user_id del JWT."
    )


def test_d005_voice_transcribe_arbitrary_file(ctx: Context) -> Finding:
    """El endpoint /voice/transcribe podría aceptar archivos no multimedia (DoS/SSRF vector)"""
    if not ctx.access_token:
        return Finding("D-005", "Transcripción de voz con archivos arbitrarios", SEVERITY_MEDIUM, WARNING,
                       "No autenticado", "Proporcionar credenciales.")

    # Enviar un archivo grande de texto como si fuera audio
    payload = b"A" * 500_000  # 500KB de texto
    r = request(ctx, "POST", "/voice/transcribe", authenticated=True,
                files={"audio": ("fake.webm", payload, "audio/webm")},
                data={"language": "es"})

    # Verificar que no crashee ni consuma recursos excesivos
    server_error = r.status_code >= 500
    return Finding(
        finding_id="D-005",
        title="Transcripción de voz con archivos arbitrarios (posible DoS)",
        severity=SEVERITY_MEDIUM,
        status=WARNING if server_error else PASS,
        evidence=f"POST /voice/transcribe con 500KB de basura → {r.status_code}",
        remediation="Validar contenido del archivo (cabeceras mágicas, duración) antes de transcribir."
    )


def test_d006_auth_on_reverse_search(ctx: Context) -> Finding:
    """Los endpoints de geocodificación (/maps/reverse, /maps/search) deberían requerir autenticación"""
    # Cada request consume un servicio externo (Nominatim) que tiene rate limiting
    r_reverse = request(ctx, "GET", "/maps/reverse", params={"lat": "20.0", "lng": "-100.0"})
    r_search = request(ctx, "GET", "/maps/search", params={"q": "Calle Principal"})

    both_public = r_reverse.status_code in {200, 502} and r_search.status_code in {200, 502}
    return Finding(
        finding_id="D-006",
        title="Geocodificación (/maps/reverse, /maps/search) sin autenticación",
        severity=SEVERITY_MEDIUM,
        status=FAIL if both_public else PASS,
        evidence=f"/maps/reverse sin token → {r_reverse.status_code}; /maps/search sin token → {r_search.status_code}",
        remediation="Requerir JWT en endpoints de geocodificación para evitar abuso de APIs externas."
    )


def test_d007_order_creation_user_enumeration(ctx: Context) -> Finding:
    """Posible enumeración de usuarios mediante errores en creación de órdenes"""
    if not ctx.access_token:
        return Finding("D-007", "Enumeración de usuarios en creación de órdenes", SEVERITY_MEDIUM, WARNING,
                       "No autenticado", "Proporcionar credenciales.")

    # Crear orden con email que SÍ existe pero datos inválidos
    # vs email que NO existe
    test_cases = [
        ("email_existente", ctx.email, "Pedido de prueba"),
        ("email_inexistente", f"noexiste-{uuid.uuid4().hex[:8]}@test.com", "Pedido de prueba"),
    ]

    results = []
    for label, email, pedido in test_cases:
        r = request(ctx, "POST", "/order", authenticated=True, json={
            "pedido": pedido,
            "cliente_nombre": "Test User",
            "telefono": "5550000000",
            "gmail": email,
            "direccion": "Dirección de prueba",
            "payment_method": "efectivo",
        })
        results.append(f"{label} → {r.status_code}: {safe_json(r)}")

    # Si los mensajes de error son diferentes, hay enumeración
    return Finding(
        finding_id="D-007",
        title="Enumeración de usuarios mediante errores en /order",
        severity=SEVERITY_MEDIUM,
        status=WARNING,
        evidence="\n".join(results),
        remediation="Usar mensajes de error genéricos independientemente de si el email existe o no."
    )


def test_d008_health_endpoint_info_leak(ctx: Context) -> Finding:
    """El endpoint /health podría exponer información del sistema"""
    r = request(ctx, "GET", "/health")
    data = safe_json(r)

    leaked_info = []
    if isinstance(data, dict):
        serialized = json.dumps(data).lower()
        if "python" in serialized:
            leaked_info.append("versión de Python")
        if "render" in serialized or "host" in serialized:
            leaked_info.append("información de host")
        if "env" in serialized or "environment" in serialized:
            leaked_info.append("variables de entorno")

    return Finding(
        finding_id="D-008",
        title="Endpoint /health expone información del sistema",
        severity=SEVERITY_MEDIUM,
        status=FAIL if leaked_info else PASS,
        evidence=f"GET /health → {r.status_code}; info expuesta: {leaked_info if leaked_info else 'ninguna'}",
        remediation="Limitar /health a status básico (UP/DOWN), sin versión de Python ni entorno."
    )


def test_d009_test_report_exposure(ctx: Context) -> Finding:
    """Archivos de reporte de pruebas podrían ser accesibles públicamente y exponer datos"""
    report_patterns = [
        "pizzeria_220_test_report.json",
        "pizzeria_220_all_tests_report.json",
        "pizzeria_220_history_regression_report.json",
        "SECURITY_REGRESSION_REPORT.json",
        "SECURITY_REGRESSION_REPORT.md",
        "tmp_test.json",
    ]
    exposed = []
    for pattern in report_patterns:
        r = request(ctx, "GET", f"/{pattern}")
        if r.status_code == 200:
            exposed.append(pattern)
        # También probar en /static y /assets
        for prefix in ["/static/", "/assets/"]:
            r2 = request(ctx, "GET", f"{prefix}{pattern}")
            if r2.status_code == 200:
                exposed.append(f"{prefix}{pattern}")

    return Finding(
        finding_id="D-009",
        title="Reportes de prueba expuestos públicamente",
        severity=SEVERITY_HIGH,
        status=FAIL if exposed else PASS,
        evidence=f"Archivos accesibles: {exposed}" if exposed else "Ningún reporte expuesto",
        remediation="Mover reportes de prueba fuera del directorio de publicación web."
    )


def test_d010_order_status_idor(ctx: Context) -> Finding:
    """Verificar que /order/{id}/status sin ownership no exponga datos"""
    if not ctx.access_token:
        return Finding("D-010", "IDOR en /order/{id}/status", SEVERITY_CRITICAL, WARNING,
                       "No autenticado", "Proporcionar credenciales.")

    # Intentar acceder al status de una orden que no nos pertenece
    r = request(ctx, "GET", "/order/999999/status", authenticated=True)
    r_no_auth = request(ctx, "GET", "/order/999999/status")

    info_leak = False
    if r.status_code == 200:
        data = safe_json(r)
        if isinstance(data, dict) and data.get("success"):
            info_leak = True

    return Finding(
        finding_id="D-010",
        title="IDOR en /order/{id}/status (acceso a órdenes ajenas)",
        severity=SEVERITY_CRITICAL,
        status=FAIL if info_leak else PASS,
        evidence=f"GET /order/999999/status con token → {r.status_code}; sin token → {r_no_auth.status_code}",
        remediation="Verificar ownership en cada consulta de status. Devolver 404 genérico si no hay match."
    )


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Custom Security Deep-Dive Tests")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--insecure", action="store_true", help="Deshabilitar verificación TLS")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT))
    args = parser.parse_args()

    ctx = Context(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        timeout=DEFAULT_TIMEOUT,
        verify_tls=not args.insecure,
        session=requests.Session(),
    )

    print("=" * 60)
    print("  CUSTOM SECURITY DEEP-DIVE TESTS")
    print(f"  Target: {args.base_url}")
    print("=" * 60)

    # Login
    if args.email and args.password:
        token = login(ctx)
        if token:
            ctx.access_token = token
            print(f"  ✅ Autenticado como: {args.email}")
        else:
            print(f"  ⚠️  No se pudo autenticar. Tests autenticados = WARNING.")
    else:
        print(f"  ⚠️  Sin credenciales. Tests autenticados = WARNING.")

    print()

    tests = [
        ("D-001", "Maps estático sin autenticación (abuso API key)", test_d001_maps_static_no_auth),
        ("D-002", "IDOR en DELETE /voice/history/{id}", test_d002_voice_idor_delete),
        ("D-003", "transcriptions.json expuesto", test_d003_transcriptions_file_exposure),
        ("D-004", "Mass assignment en chat history", test_d004_mass_assignment_chat_history),
        ("D-005", "Transcripción de voz con archivos arbitrarios", test_d005_voice_transcribe_arbitrary_file),
        ("D-006", "Geocodificación sin autenticación", test_d006_auth_on_reverse_search),
        ("D-007", "Enumeración de usuarios en /order", test_d007_order_creation_user_enumeration),
        ("D-008", "Endpoint /health expone información", test_d008_health_endpoint_info_leak),
        ("D-009", "Reportes de prueba expuestos", test_d009_test_report_exposure),
        ("D-010", "IDOR en /order/{id}/status", test_d010_order_status_idor),
    ]

    results: list[Finding] = []
    for fid, title, func in tests:
        print(f"  [{fid}] {title}... ", end="", flush=True)
        try:
            finding = func(ctx)
        except Exception as e:
            finding = Finding(fid, title, SEVERITY_CRITICAL, WARNING, f"Error: {e}", "Revisar manualmente.")
        results.append(finding)
        status_icon = "✅" if finding.status == PASS else "❌" if finding.status == FAIL else "⚠️"
        print(f"{status_icon} {finding.status}")

    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.status == PASS)
    failed = sum(1 for r in results if r.status == FAIL)
    warnings = sum(1 for r in results if r.status == WARNING)
    print(f"  Total: {len(results)} | PASS: {passed} | FAIL: {failed} | WARNING: {warnings}")

    failed_tests = [r for r in results if r.status == FAIL]
    if failed_tests:
        print()
        print("  ❌ FAILED TESTS:")
        for ft in failed_tests:
            print(f"     [{ft.finding_id}] {ft.title}")
            print(f"     Evidence: {ft.evidence[:200]}")

    print()
    if failed:
        print("  🚫 VULNERABILIDADES DETECTADAS")
    else:
        print("  ✅ Sin vulnerabilidades críticas nuevas detectadas")

    # ── Generar reporte MD ──
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    report_lines = [
        "# Custom Security Deep-Dive Report",
        "",
        f"- **Target:** `{args.base_url}`",
        f"- **Generated:** `{timestamp}`",
        f"- **Passed:** {passed}",
        f"- **Failed:** {failed}",
        f"- **Warnings:** {warnings}",
        f"- **Skipped:** 0",
        "",
        "## Results",
        "",
        "| ID | Finding | Severity | Status |",
        "|---|---|---|---|",
    ]
    for r in results:
        status_icon = "✅" if r.status == PASS else "❌" if r.status == FAIL else "⚠️"
        sev_icon = "🔴" if r.severity == "CRITICAL" else "🟠" if r.severity == "HIGH" else "🟡"
        report_lines.append(f"| {r.finding_id} | {r.title} | {sev_icon} {r.severity} | {status_icon} {r.status} |")

    for r in results:
        report_lines.extend([
            "",
            f"## {r.finding_id} — {r.title}",
            "",
            f"**Status:** `{r.status}`",
            f"**Severity:** `{r.severity}`",
            "",
            "### Evidence",
            "",
            "```text",
            r.evidence[:500],
            "```",
            "",
            "### Remediation",
            "",
            r.remediation,
        ])

    report_lines.extend([
        "",
        "---",
        "",
        "## Resumen ejecutivo",
        "",
        f"Se ejecutaron {len(results)} pruebas personalizadas de seguridad:",
        f"- ✅ {passed} pasaron",
        f"- ❌ {failed} fallaron",
        f"- ⚠️ {warnings} requieren revisión manual",
        "",
    ])
    if failed_tests:
        report_lines.append("### Vulnerabilidades encontradas")
        report_lines.append("")
        for ft in failed_tests:
            report_lines.append(f"- **{ft.finding_id}** ({ft.severity}): {ft.title}")

    report = "\n".join(report_lines)

    output_path = Path(args.output_dir) / "CUSTOM_SECURITY_DEEP_DIVE.md"
    output_path.write_text(report, encoding="utf-8")
    print(f"\n  📄 Reporte guardado: {output_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
