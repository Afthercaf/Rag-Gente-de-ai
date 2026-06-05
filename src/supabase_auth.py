# src/supabase_auth.py

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL no definida")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY no definida")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def register_user(
    nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    role: str = "cliente",
    password_hash: str = ""
):
    try:
        payload = {
            "nombre": nombre,
            "telefono": telefono,
            "gmail": gmail.strip().lower(),
            "direccion": direccion,
            "role": role,
            "password_hash": password_hash
        }

        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=HEADERS,
            json=payload
        )

        logger.info(f"REGISTER STATUS: {response.status_code}")
        logger.info(response.text)

        if response.status_code in (200, 201):
            data = response.json()
            return data[0] if data else None

        return None

    except Exception as e:
        logger.exception(f"Error registrando usuario: {e}")
        return None


def login_user(gmail: str, password_hash: str):
    try:
        gmail = gmail.strip().lower()

        params = {
            "gmail": f"eq.{gmail}",
            "password_hash": f"eq.{password_hash}",
            "select": "*"
        }

        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=HEADERS,
            params=params
        )

        logger.info(f"LOGIN STATUS: {response.status_code}")
        logger.info(response.text)

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            logger.warning("Usuario o contraseña incorrectos")
            return None

        return data[0]

    except Exception as e:
        logger.exception(f"Error en login: {e}")
        return None


def get_user_by_gmail(gmail: str):
    try:
        gmail = gmail.strip().lower()

        params = {
            "gmail": f"eq.{gmail}",
            "select": "*"
        }

        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=HEADERS,
            params=params
        )

        if response.status_code != 200:
            return None

        data = response.json()

        return data[0] if data else None

    except Exception as e:
        logger.exception(f"Error obteniendo usuario: {e}")
        return None