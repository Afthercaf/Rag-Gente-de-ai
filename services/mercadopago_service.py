"""
Servicio de Mercado Pago - Integración Dinámica para el Chat
"""

import os
import logging
import json
import hmac
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

import mercadopago
import redis
import core.config  # Carga centralizada del entorno.
from core.config import require_env
from core.crypto import decrypt_json, derive_aes_key, encrypt_json
from core.session_store import REDIS_URL

logger = logging.getLogger(__name__)


class PaymentStatus(str, Enum):
    """Estados posibles de un pago en Mercado Pago"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    IN_PROCESS = "in_process"
    ON_HOLD = "on_hold"


class PaymentMethod(str, Enum):
    """Métodos de pago soportados"""
    CARD = "card"
    PIX = "pix"
    OXXO = "oxxo"
    BANK_TRANSFER = "bank_transfer"
    MERCADO_PAGO = "mercadopago"


@dataclass
class PaymentResult:
    """Resultado completo de un pago"""
    success: bool
    payment_id: Optional[str] = None
    status: Optional[str] = None
    status_detail: Optional[str] = None
    transaction_amount: Optional[float] = None
    payment_method_id: Optional[str] = None
    qr_code: Optional[str] = None
    qr_code_base64: Optional[str] = None
    ticket_url: Optional[str] = None
    external_reference: Optional[str] = None
    date_created: Optional[str] = None
    date_approved: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None
    is_test: bool = True
    
    def to_message(self) -> str:
        """Convierte el resultado a un mensaje para el chat"""
        if not self.success:
            return f"❌ Error en el pago: {self.error_message or 'Intenta nuevamente'}"
        
        if self.status == "approved":
            return f"✅ ¡Pago aprobado! ID: {self.payment_id}\nGracias por tu compra 🍕"
        
        if self.status == "pending":
            msg = f"⏳ Pago pendiente de confirmación (ID: {self.payment_id})\n"
            if self.qr_code:
                msg += f"📱 Código QR: {self.qr_code}\n"
            if self.ticket_url:
                msg += f"🎫 Ticket: {self.ticket_url}\n"
            msg += "⚠️ Recuerda: El pago debe completarse dentro de los próximos 30 minutos"
            return msg
        
        return f"⚠️ Estado del pago: {self.status}\nDetalle: {self.status_detail}"


@dataclass
class PaymentLink:
    """Link de pago generado dinámicamente"""
    url: str
    payment_id: str
    status: str
    amount: float
    description: str
    expires_at: Optional[str] = None
    short_url: Optional[str] = None
    
    def to_message(self) -> str:
        """Convierte el link a un mensaje para el chat"""
        msg = f"🔗 **Link de pago generado**\n"
        msg += f"💰 Monto: ${self.amount:.2f}\n"
        msg += f"📝 Descripción: {self.description}\n"
        msg += f"📲 **URL:** {self.url}\n"
        if self.expires_at:
            msg += f"⏰ Expira: {self.expires_at}\n"
        return msg


@dataclass
class PaymentSession:
    """Sesión de pago para un usuario"""
    user_id: int
    order_id: str
    amount: float
    description: str
    status: PaymentStatus
    payment_id: Optional[str] = None
    qr_code: Optional[str] = None
    payment_link: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=30))
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    attempts: int = 0
    
    def is_expired(self) -> bool:
        """Verifica si la sesión ha expirado"""
        return datetime.now() > self.expires_at
    
    def time_left(self) -> int:
        """Minutos restantes antes de que expire"""
        if self.is_expired():
            return 0
        return (self.expires_at - datetime.now()).seconds // 60


class MercadoPagoService:
    """Servicio dinámico para integración con el chat"""

    def __init__(self):
        # Cargar credenciales
        self.access_token = require_env("MERCADO_PAGO_ACCESS_TOKEN")
        self.public_key = require_env("MERCADO_PAGO_PUBLIC_KEY")
        self.mode = os.getenv("MERCADO_PAGO_MODE", "sandbox")
        self.callback_url = require_env("MERCADO_PAGO_CALLBACK_URL")
        # Opcional al arrancar: si falta, verify_webhook_signature rechaza
        # todos los webhooks (fail closed) sin deshabilitar pagos salientes.
        self.webhook_secret = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET")
        self.test_user = os.getenv("MERCADO_PAGO_TEST_USER")
        self.test_password = os.getenv("MERCADO_PAGO_TEST_PASSWORD")
        
        # Sesiones persistentes en Redis, cifradas y con TTL.
        self._session_redis = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        self._session_key = derive_aes_key(
            require_env("SESSION_ENCRYPTION_KEY", min_length=32),
            b"pizzeria220-payment-session-v1",
        )
        self._payment_history: List[Dict] = []
        
        # Validar callback URL
        self._has_public_callback_url = bool(self.callback_url) and not any(
            host in self.callback_url for host in ("localhost", "127.0.0.1", "0.0.0.0")
        )
        
        if not self._has_public_callback_url:
            logger.warning(
                "⚠️ MERCADO_PAGO_CALLBACK_URL apunta a una URL local (%s). "
                "Se omitirá notification_url en los pagos; para recibir webhooks "
                "en desarrollo usa una URL pública (ej. ngrok) y configúrala en "
                "MERCADO_PAGO_CALLBACK_URL.",
                self.callback_url,
            )
        
        # Inicializar SDK
        if not self.access_token:
            logger.warning("⚠️ MERCADO_PAGO_ACCESS_TOKEN no configurado")
            self.sdk = None
        else:
            try:
                self.sdk = mercadopago.SDK(self.access_token)
                logger.info(f"✅ Mercado Pago configurado en modo: {self.mode}")
                self._log_credentials()
            except Exception as e:
                logger.error(f"❌ Error inicializando SDK: {e}")
                self.sdk = None

    def _log_credentials(self):
        """Registra el estado de las credenciales de Mercado Pago sin exponer valores."""
        logger.info("=" * 70)
        logger.info("🔍 Verificando credenciales de Mercado Pago")
        logger.info("Access Token configurado: %s", bool(self.access_token))
        logger.info("Public Key configurada: %s", bool(self.public_key))
        logger.info("Modo: %s", self.mode)
        logger.info("Callback URL: %s", self.callback_url)
        logger.info("Webhook secret configurado: %s", bool(self.webhook_secret))
        logger.info("=" * 70)

    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.sdk is not None

    def is_sandbox(self) -> bool:
        """Verifica si está en modo sandbox"""
        return self.mode == "sandbox"

    @staticmethod
    def _redis_session_key(order_id: str) -> str:
        return f"payment-session:{order_id}"

    def _save_session(self, session: PaymentSession) -> None:
        payload = {
            "user_id": session.user_id,
            "order_id": session.order_id,
            "amount": session.amount,
            "description": session.description,
            "status": session.status.value,
            "payment_id": session.payment_id,
            "qr_code": session.qr_code,
            "payment_link": session.payment_link,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "user_email": session.user_email,
            "user_name": session.user_name,
            "attempts": session.attempts,
        }
        ttl = max(1, int((session.expires_at - datetime.now()).total_seconds()))
        self._session_redis.setex(
            self._redis_session_key(session.order_id),
            ttl,
            encrypt_json(payload, self._session_key),
        )

    def _load_session(self, order_id: str) -> Optional[PaymentSession]:
        encrypted = self._session_redis.get(self._redis_session_key(order_id))
        if not encrypted:
            return None
        payload = decrypt_json(encrypted, self._session_key)
        if not payload:
            self._session_redis.delete(self._redis_session_key(order_id))
            return None
        return PaymentSession(
            user_id=int(payload["user_id"]),
            order_id=str(payload["order_id"]),
            amount=float(payload["amount"]),
            description=str(payload["description"]),
            status=PaymentStatus(payload["status"]),
            payment_id=payload.get("payment_id"),
            qr_code=payload.get("qr_code"),
            payment_link=payload.get("payment_link"),
            created_at=datetime.fromisoformat(payload["created_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            user_email=payload.get("user_email"),
            user_name=payload.get("user_name"),
            attempts=int(payload.get("attempts", 0)),
        )

    def get_test_credentials(self) -> Dict:
        """Retorna información no sensible del modo de prueba."""
        return {
            "mode": self.mode,
            "available": self.is_available(),
        }

    def create_payment_session(
        self,
        user_id: int,
        order_id: str,
        amount: float,
        description: str,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Optional[PaymentSession]:
        """Crea una sesión de pago para un usuario"""
        if not self.is_available():
            logger.error("❌ Servicio no disponible")
            return None
        
        existing = self._load_session(order_id)
        if existing and not existing.is_expired():
            logger.info(f"⚠️ Ya existe una sesión activa para {order_id}")
            return existing
        
        session = PaymentSession(
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            description=description,
            status=PaymentStatus.PENDING,
            user_email=user_email,
            user_name=user_name,
        )
        self._save_session(session)
        logger.info(f"✅ Sesión de pago creada: {order_id} - ${amount:.2f}")
        return session

    def get_session(self, order_id: str) -> Optional[PaymentSession]:
        """Obtiene una sesión de pago"""
        session = self._load_session(order_id)
        if session and session.is_expired():
            logger.info(f"⏰ Sesión expirada: {order_id}")
            session.status = PaymentStatus.CANCELLED
            self._save_session(session)
        return session

    def update_session(self, order_id: str, payment_id: str, status: PaymentStatus):
        """Actualiza una sesión de pago"""
        session = self._load_session(order_id)
        if session:
            session.payment_id = payment_id
            session.status = status
            session.attempts += 1
            self._save_session(session)
            logger.info(f"🔄 Sesión actualizada: {order_id} -> {status.value}")

    def create_payment(
        self,
        amount: float,
        description: str,
        order_id: str,
        user_email: str,
        user_name: str,
        payment_method: str = "mercadopago",
    ) -> PaymentResult:
        """
        Crea un pago dinámico en Mercado Pago
        """
        if not self.is_available():
            return PaymentResult(
                success=False,
                error_message="❌ Servicio de Mercado Pago no disponible"
            )

        try:
            if amount <= 0:
                return PaymentResult(
                    success=False,
                    error_message="❌ El monto debe ser mayor a 0"
                )

            payer = {"email": user_email}

            payment_data = {
                "transaction_amount": float(amount),
                "description": description[:255],
                "payer": payer,
                "external_reference": order_id,
                "statement_descriptor": "PIZZERIA 220",
                "binary_mode": True,
            }
            
            if self._has_public_callback_url:
                payment_data["notification_url"] = self.callback_url

            payment_data["payment_method_id"] = self._get_payment_method_id(payment_method)

            logger.info(f"💳 Creando pago: ${amount:.2f} - {description} (Método: {payment_method})")
            
            if self.is_sandbox():
                logger.info(f"🔬 [SANDBOX] Pago de prueba")

            response = self.sdk.payment().create(payment_data)
            response_data = response.get("response", {})
            status = response.get("status", "error")

            if status != 201:
                error_msg = response_data.get("message", "Error desconocido")
                logger.error(f"❌ Error creando pago: {error_msg}")
                logger.debug(
                    "Mercado Pago rechazó la creación; status=%s code=%s",
                    status,
                    response_data.get("error") or response_data.get("status"),
                )
                return PaymentResult(
                    success=False,
                    error_message=error_msg,
                    raw_response=response_data,
                )

            self.update_session(
                order_id=order_id,
                payment_id=str(response_data.get("id")),
                status=PaymentStatus.PENDING,
            )

            self._payment_history.append({
                "order_id": order_id,
                "payment_id": response_data.get("id"),
                "amount": amount,
                "status": response_data.get("status"),
                "created_at": datetime.now().isoformat(),
            })

            result = self._parse_payment_response(response_data)
            logger.info(f"✅ Pago creado: ID={result.payment_id}, Estado={result.status}")

            return result

        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}", exc_info=True)
            return PaymentResult(
                success=False,
                error_message="No fue posible crear el pago.",
            )

    def create_payment_link(
        self,
        amount: float,
        description: str,
        order_id: str,
        email: str,
        name: str,
        title: str = "Pago Pizzería 220",
        expires_in_minutes: int = 30,
        user_id: int = 0,
    ) -> Optional[PaymentLink]:
        """
        Crea un link de pago dinámico (preferencia)
        """
        logger.info(f"🔗 [create_payment_link] Iniciando creación de link")
        logger.info(f"   - amount: {amount}")
        logger.info(f"   - description: {description}")
        logger.info(f"   - order_id: {order_id}")
        logger.info(f"   - email: {email}")
        logger.info(f"   - user_id: {user_id}")
        
        if not self.is_available():
            logger.error("❌ Servicio de Mercado Pago no disponible")
            return None

        try:
            # ================================================================
            # 🔧 CORREGIDO: Usar timezone.utc para fechas
            # ================================================================
            now_utc = datetime.now(timezone.utc)
            expires_at_utc = now_utc + timedelta(minutes=expires_in_minutes)
            
            logger.info(f"🕐 Hora UTC actual: {now_utc.isoformat()}")
            logger.info(f"🕐 Expira a las UTC: {expires_at_utc.isoformat()}")

            # ================================================================
            # 🔧 CORREGIDO: Construir preferencia con fechas UTC
            # ================================================================
            preference_data = {
                "items": [
                    {
                        "title": title,
                        "description": description[:255],
                        "quantity": 1,
                        "currency_id": "MXN",
                        "unit_price": float(amount),
                    }
                ],
                "payer": {
                    "name": name,
                    "email": email,
                },
                "external_reference": str(order_id),
                "statement_descriptor": "PIZZERIA 220",
                "expires": True,
                "expiration_date_from": now_utc.isoformat(timespec='seconds'),
                "expiration_date_to": expires_at_utc.isoformat(timespec='seconds'),
            }

            # Agregar back_urls y notification_url solo si es una URL pública
            if self._has_public_callback_url:
                base_url = self.callback_url.rstrip('/')
                preference_data["back_urls"] = {
                    "success": f"{base_url}/success?order_id={order_id}",
                    "failure": f"{base_url}/failure?order_id={order_id}",
                    "pending": f"{base_url}/pending?order_id={order_id}",
                }
                preference_data["auto_return"] = "approved"
                preference_data["notification_url"] = f"{base_url}/webhook"

            logger.info(f"📤 Enviando preferencia a Mercado Pago...")
            logger.info(f"   Datos: {json.dumps(preference_data, indent=2, default=str)}")
            
            if self.is_sandbox():
                logger.info(f"🔬 [SANDBOX] Link de pago de prueba")

            # Crear la preferencia
            response = self.sdk.preference().create(preference_data)
            
            logger.info(f"📦 Status de respuesta: {response.get('status')}")
            
            response_data = response.get("response", {})
            status = response.get("status", "error")

            if status != 201:
                error_msg = response_data.get("message", "Error desconocido")
                logger.error(f"❌ Error creando link: {error_msg}")
                logger.error(f"📦 Response completo: {response_data}")
                return None

            # Verificar si la preferencia expiró
            if response_data.get("preference_expired") is True:
                logger.error("❌ La preferencia se creó con estado 'expired'")
                logger.error(f"📦 Datos de expiración: {response_data.get('expiration_date_from')} -> {response_data.get('expiration_date_to')}")
                # No retornamos None, pero registramos el error
                # El link podría funcionar igual

            link = PaymentLink(
                url=response_data.get("init_point"),
                payment_id=response_data.get("id"),
                status=response_data.get("status", "pending"),
                amount=amount,
                description=description,
                expires_at=expires_at_utc.isoformat(),
                short_url=response_data.get("sandbox_init_point") if self.is_sandbox() else None,
            )

            # Crear sesión asociada
            self.create_payment_session(
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                description=description,
                user_email=email,
                user_name=name,
            )

            logger.info(f"✅ Link de pago creado: {link.url}")
            logger.info(f"   - Payment ID: {link.payment_id}")
            logger.info(f"   - Status: {link.status}")
            logger.info(f"   - Expira: {link.expires_at}")
            return link

        except Exception as e:
            logger.error(f"❌ Error creando link: {e}", exc_info=True)
            return None

    def get_payment_status(self, payment_id: str) -> Optional[Dict]:
        """Obtiene el estado actual de un pago"""
        if not self.is_available():
            return None

        try:
            response = self.sdk.payment().get(payment_id)
            response_data = response.get("response", {})
            status = response.get("status", "error")

            if status != 200:
                logger.error(f"❌ Error obteniendo pago {payment_id}")
                return None

            return {
                "id": response_data.get("id"),
                "status": response_data.get("status"),
                "status_detail": response_data.get("status_detail"),
                "amount": response_data.get("transaction_amount"),
                "payment_method": response_data.get("payment_method_id"),
                "date_approved": response_data.get("date_approved"),
                "external_reference": response_data.get("external_reference"),
            }

        except Exception as e:
            logger.error(f"❌ Error obteniendo estado: {e}")
            return None

    def check_and_update_session(self, order_id: str) -> Optional[Dict]:
        """
        Verifica el estado de un pago y actualiza la sesión
        """
        session = self._load_session(order_id)
        if not session or not session.payment_id:
            return None

        status_data = self.get_payment_status(session.payment_id)
        if status_data:
            new_status = PaymentStatus(status_data.get("status", "pending"))
            session.status = new_status
            self._save_session(session)

            return {
                "order_id": order_id,
                "payment_id": session.payment_id,
                "status": new_status.value,
                "status_detail": status_data.get("status_detail"),
                "amount": session.amount,
            }

        return None

    def cancel_session(self, order_id: str) -> bool:
        """Cancela una sesión de pago"""
        session = self._load_session(order_id)
        if session:
            session.status = PaymentStatus.CANCELLED
            self._save_session(session)
            logger.info(f"❌ Sesión cancelada: {order_id}")
            return True
        return False

    def get_active_session_message(self, order_id: str) -> str:
        """Genera un mensaje para mostrar al usuario sobre su sesión de pago"""
        session = self._load_session(order_id)
        if not session:
            return "No hay un pago activo para este pedido."

        if session.status == PaymentStatus.APPROVED:
            return f"✅ ¡Pago aprobado! Pedido {order_id} confirmado. ¡Gracias! 🍕"

        if session.status == PaymentStatus.REJECTED:
            return f"❌ El pago fue rechazado. Por favor intenta nuevamente."

        if session.is_expired():
            return f"⏰ El tiempo para pagar expiró. Por favor inicia un nuevo pago."

        time_left = session.time_left()
        
        message = f"""
💰 **Pago pendiente - Pedido {order_id}**
Monto: ${session.amount:.2f}
Tiempo restante: {time_left} minutos

📲 **Opciones de pago:**
1. Paga con Mercado Pago (tarjeta o QR)
2. Paga en efectivo en el local

¿Cómo deseas pagar?
"""
        
        if session.payment_link:
            message += f"\n🔗 Link de pago: {session.payment_link}"
        
        if session.qr_code:
            message += f"\n📱 QR Code: {session.qr_code}"
        
        return message

    def get_payment_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene el historial de pagos"""
        return self._payment_history[-limit:]

    def _get_payment_method_id(self, method: str) -> str:
        """Mapea el método de pago al ID de Mercado Pago"""
        mapping = {
            "card": "card",
            "pix": "pix",
            "oxxo": "oxxo",
            "mercadopago": "bank_transfer",
            "bank_transfer": "bank_transfer",
            "transfer": "bank_transfer",
        }
        return mapping.get(method.lower(), "bank_transfer")

    def verify_webhook_signature(
        self,
        *,
        signature_header: Optional[str],
        request_body: bytes,
    ) -> bool:
        """Verifica la firma x-signature enviada por Mercado Pago.

        VULN-22: rechazar webhooks cuya firma no coincida con el secreto.
        """
        if not self.webhook_secret or not signature_header:
            return False

        try:
            parts = {
                part.split("=")[0]: part.split("=", 1)[1]
                for part in signature_header.split(",")
                if "=" in part
            }
            timestamp = parts.get("ts", "")
            signature = parts.get("v1", "")

            if not timestamp or not signature:
                return False

            template_id = ""
            body_text = request_body.decode("utf-8", errors="replace")
            # Extraer id del JSON del body para preferencias/pagos.
            try:
                payload = json.loads(body_text)
                data_id = payload.get("data", {}).get("id")
                if not data_id:
                    data_id = payload.get("id")
                template_id = str(data_id) if data_id else ""
            except Exception:
                pass

            signed_payload = (
                f"{timestamp}.{template_id}.{body_text}"
                if template_id
                else f"{timestamp}.{body_text}"
            )
            expected = hmac.new(
                self.webhook_secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected, signature)
        except Exception as exc:
            logger.warning("Error verificando firma de webhook: %s", exc)
            return False

    def _parse_payment_response(self, response_data: Dict) -> PaymentResult:
        """Parsea la respuesta de Mercado Pago"""
        transaction_data = (
            response_data.get("point_of_interaction", {})
            .get("transaction_data", {})
        ) or {}

        return PaymentResult(
            success=response_data.get("status") in ("approved", "pending"),
            payment_id=str(response_data.get("id")) if response_data.get("id") else None,
            status=response_data.get("status"),
            status_detail=response_data.get("status_detail"),
            transaction_amount=response_data.get("transaction_amount"),
            payment_method_id=response_data.get("payment_method_id"),
            qr_code=response_data.get("qr_code") or transaction_data.get("qr_code"),
            qr_code_base64=response_data.get("qr_code_base64") or transaction_data.get("qr_code_base64"),
            ticket_url=response_data.get("ticket_url") or transaction_data.get("ticket_url"),
            external_reference=response_data.get("external_reference"),
            date_created=response_data.get("date_created"),
            date_approved=response_data.get("date_approved"),
            raw_response=response_data,
            is_test=self.is_sandbox(),
        )

    def get_payment_methods(self) -> Dict[str, str]:
        """Obtiene los métodos de pago disponibles"""
        return {
            "card": "Tarjeta de crédito/débito",
            "bank_transfer": "Transferencia bancaria (QR)",
            "pix": "PIX (Brasil)",
            "oxxo": "OXXO (México)",
        }


# Instancia global
mercadopago_service = MercadoPagoService()

# Log de inicio
if mercadopago_service.is_available():
    logger.info("=" * 70)
    logger.info("✅ Servicio de Mercado Pago inicializado correctamente")
    logger.info(f"   Modo: {mercadopago_service.mode.upper()}")
    if mercadopago_service.is_sandbox():
        logger.info("   🔬 Modo SANDBOX activo - Pagos de prueba")
        logger.info(f"   👤 Usuario de prueba: {mercadopago_service.test_user}")
    logger.info("=" * 70)
else:
    logger.warning("⚠️ Servicio de Mercado Pago NO disponible")
    logger.warning("   Verifica que MERCADO_PAGO_ACCESS_TOKEN esté configurado")
