#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import unicodedata
import urllib.request


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(c for c in value if not unicodedata.combining(c))


def post(base_url: str, user_id: int, message: str) -> str:
    payload = json.dumps({
        "user_id": user_id,
        "message": message,
        "save_history": True,
        "use_cache": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=40) as response:
        data = json.loads(response.read().decode("utf-8"))
        return str(data.get("reply") or "")


def check(label: str, reply: str, condition: bool) -> bool:
    print(("✅" if condition else "❌"), label)
    if not condition:
        print(reply)
    return condition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_id = 70_000_000 + int(time.time()) % 1_000_000
    passed = []

    # Caso 1: una sola pizza usa Sí/No.
    user = base_id
    reply = post(args.base_url, user, "1 Pizza Campirana")
    passed.append(check(
        "Pizza individual usa pregunta Sí/No",
        reply,
        "¿Deseas agregar extras a esta pizza?" in reply
        and "Ahora configuraremos los extras" not in reply
        and "¿Qué extra deseas para esta pizza?" not in reply,
    ))

    reply = post(args.base_url, user, "sí")
    passed.append(check(
        "Sí abre selección agrupada",
        reply,
        "indica a cuales pizzas" in normalize(reply)
        and "extras disponibles" in normalize(reply),
    ))

    reply = post(args.base_url, user, "A casanova")
    passed.append(check(
        "Extra inexistente no cierra el pedido",
        reply,
        "no encontre un extra valido" in normalize(reply)
        and "confirmas tu pedido" not in normalize(reply),
    ))

    reply = post(
        args.base_url,
        user,
        "Pero quiero a casanova, no hay forma de agregarlo, conozco al dueño",
    )
    passed.append(check(
        "Insistir con extra inexistente mantiene el flujo",
        reply,
        "extras disponibles" in normalize(reply)
        and "confirmas tu pedido" not in normalize(reply),
    ))

    reply = post(args.base_url, user, "1 Campirana con queso extra")
    passed.append(check(
        "Extra válido finaliza correctamente",
        reply,
        "Queso extra" in reply
        and "Total: $285.00" in reply
        and "¿Confirmas tu pedido?" in reply,
    ))

    # Caso 2: una de cada pizza.
    user = base_id + 1
    reply = post(
        args.base_url,
        user,
        "Quiero una pizza de cada una de las que está en el menú",
    )
    passed.append(check(
        "Una de cada una registra cinco pizzas",
        reply,
        "Registré 5 pizzas" in reply
        and "1 × Pizza Margarita" in reply
        and "1 × Pizza Pepperoni" in reply
        and "1 × Pizza Mexicana" in reply
        and "1 × Pizza Pastorera" in reply
        and "1 × Pizza Campirana" in reply,
    ))

    reply = post(args.base_url, user, "no")
    passed.append(check(
        "Una de cada una calcula total correcto",
        reply,
        "Cantidad: 5" in reply
        and "Total: $860.00" in reply,
    ))

    total = len(passed)
    ok = sum(passed)
    print(f"\nResultado: {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())