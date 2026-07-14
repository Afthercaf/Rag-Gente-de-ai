#!/usr/bin/env python3
"""
Script de Sembrado de Datos de Estrés - Semana 7
Puebla la base de datos SQLite y ChromaDB con 10,000+ registros realistas.

Requisitos rúbrica:
- Mínimo 10,000 registros (Nivel Competente)
- 50,000+ registros (Nivel Excelente)
- Uso de transacciones/bulk inserts optimizados
- Índices B-Tree en columnas consultadas
- Índices HNSW en ChromaDB para búsqueda vectorial

Uso:
    python seed_data.py              # 10,000 registros
    python seed_data.py --full       # 50,000 registros (Excelente)
    python seed_data.py --verify     # Solo verifica conteos
"""

import argparse
import sys
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configurar path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import (
    create_engine, text, Column, Integer, String, Float, DateTime, Boolean, Index
)
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ==================== CONFIGURACIÓN ====================

DB_PATH = "sqlite:///D:/rag/tcg_cards.db"
CHROMA_PATH = "D:/rag/chroma"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384 dims, rápido y bueno

# Datos realistas para pizzería
PIZZAS = [
    ("Pizza Margarita", "Queso mozzarella, salsa de tomate, albahaca fresca", 180.00),
    ("Pizza Pepperoni", "Queso mozzarella, salsa de tomate, pepperoni", 210.00),
    ("Pizza Hawaiana", "Queso mozzarella, salsa de tomate, jamón, piña", 220.00),
    ("Pizza Cuatro Quesos", "Mozzarella, gorgonzola, parmesano, provolone", 240.00),
    ("Pizza Vegetariana", "Queso mozzarella, salsa de tomate, pimientos, cebolla, champiñones, aceitunas", 215.00),
    ("Pizza Barbacoa", "Queso mozzarella, salsa BBQ, pollo, cebolla, bacon", 230.00),
    ("Pizza Carbonara", "Queso mozzarella, nata, bacon, cebolla, champiñones", 225.00),
    ("Pizza Mexicana", "Queso mozzarella, salsa de tomate, jalapeños, carne molida, maíz", 235.00),
    ("Pizza Napolitana", "Queso mozzarella, salsa de tomate, anchoas, alcaparras, orégano", 240.00),
    ("Pizza Prosciutto", "Queso mozzarella, salsa de tomate, jamón serrano, rúcula, parmesano", 250.00),
    ("Pizza Funghi", "Queso mozzarella, salsa de tomate, champiñones variados, trufa", 230.00),
    ("Pizza Diavola", "Queso mozzarella, salsa de tomate, salami picante, nduja", 235.00),
    ("Pizza Capricciosa", "Queso mozzarella, salsa de tomate, jamón, alcachofas, champiñones, aceitunas", 245.00),
    ("Pizza Tonno", "Queso mozzarella, salsa de tomate, atún, cebolla, aceitunas", 220.00),
    ("Pizza Parma", "Queso mozzarella, salsa de tomate, jamón de Parma, rúcula, lascas de parmesano", 260.00),
]

EXTRAS = [
    ("Queso extra", 45.00),
    ("Pepperoni extra", 50.00),
    ("Champiñones", 35.00),
    ("Cebolla caramelizada", 30.00),
    ("Pimientos", 30.00),
    ("Aceitunas", 25.00),
    ("Jalapeños", 25.00),
    ("Bacon", 55.00),
    ("Jamón serrano", 60.00),
    ("Rúcula", 35.00),
    ("Piña", 30.00),
    ("Anchoas", 50.00),
    ("Alcaparras", 30.00),
    ("Huevo", 25.00),
    ("Trufa", 80.00),
]

TAMAÑOS = ["Personal", "Mediana", "Grande", "Familiar"]
TAMAÑO_MULT = {"Personal": 0.7, "Mediana": 1.0, "Grande": 1.3, "Familiar": 1.6}

PROMOCIONES = [
    ("2x1 Martes", "Todos los martes: 2 pizzas medianas al precio de 1", "martes"),
    ("Combo Familiar", "2 pizzas grandes + 2 refrescos + postre", "diario"),
    ("Mediodía Express", "Pizza personal + refresco por $150 MXN (lunes-viernes 13-16h)", "dias_laborables"),
    ("Fin de Semana", "20% descuento en pizzas familiares sábados y domingos", "finde"),
    ("Cumpleañero", "Pizza gratis en tu cumpleaños (con compra mínima $300)", "eventos"),
    ("Estudiante", "15% descuento mostrando credencial vigente", "diario"),
    ("App Móvil", "10% descuento extra pedidos por la app", "diario"),
]

NOMBRES = [
    "Alejandro", "María", "Carlos", "Ana", "Luis", "Laura", "Pedro", "Sofía",
    "Jorge", "Isabel", "Manuel", "Carmen", "Francisco", "Patricia", "Antonio",
    "Elena", "Miguel", "Rosa", "David", "Silvia", "Javier", "Teresa", "Daniel",
    "Cristina", "Pablo", "Mónica", "Andrés", "Paula", "Sergio", "Lucía",
]

APELLIDOS = [
    "García", "Rodríguez", "González", "Fernández", "López", "Martínez",
    "Sánchez", "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz", "Hernández",
    "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez",
    "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez",
]

CALLES = [
    "Av. Insurgentes", "Calle Reforma", "Av. Universidad", "Calle Morelos",
    "Av. Juárez", "Calle Hidalgo", "Av. Chapultepec", "Calle Allende",
    "Av. Tamaulipas", "Calle Querétaro", "Av. Veracruz", "Calle Puebla",
    "Av. Oaxaca", "Calle Chiapas", "Av. Yucatán", "Calle Quintana Roo",
]

COLONIAS = [
    "Roma Norte", "Condesa", "Del Valle", "Nápoles", "Polanco", "Anzures",
    "Escandón", "San Rafael", "Santa María la Ribera", "Doctores", "Obrera",
    "Portales", "Narvarte", "Letrán Valle", "Granada", "Crédito Constructor",
]

CIUDADES = ["Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Tijuana"]
ESTADOS = ["CDMX", "JAL", "NL", "PUE", "BCN"]

Base = declarative_base()


class Pedido(Base):
    __tablename__ = "pedidos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_nombre = Column(String(100), nullable=False, index=True)
    cliente_telefono = Column(String(20), nullable=False, index=True)
    cliente_email = Column(String(100), index=True)
    direccion = Column(String(200))
    colonia = Column(String(100), index=True)
    ciudad = Column(String(50), index=True)
    estado = Column(String(10), index=True)
    codigo_postal = Column(String(10))
    
    pizza_nombre = Column(String(100), nullable=False, index=True)
    tamaño = Column(String(20), nullable=False, index=True)
    ingredientes_quitados = Column(String(200))
    extras = Column(String(200))
    
    subtotal = Column(Float, nullable=False)
    descuento = Column(Float, default=0.0)
    total = Column(Float, nullable=False, index=True)
    
    metodo_pago = Column(String(30), index=True)
    estado_pago = Column(String(20), default="pendiente", index=True)
    estado_pedido = Column(String(20), default="nuevo", index=True)
    
    fecha_creacion = Column(DateTime, default=datetime.now, index=True)
    fecha_actualizacion = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    notas = Column(String(500))

    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        Index('idx_pedido_cliente_fecha', 'cliente_telefono', 'fecha_creacion'),
        Index('idx_pedido_estado_fecha', 'estado_pedido', 'fecha_creacion'),
        Index('idx_pedido_pizza_tamaño', 'pizza_nombre', 'tamaño'),
    )


class Cliente(Base):
    __tablename__ = "clientes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    telefono = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(100), index=True)
    direccion = Column(String(200))
    colonia = Column(String(100))
    ciudad = Column(String(50))
    estado = Column(String(10))
    codigo_postal = Column(String(10))
    fecha_registro = Column(DateTime, default=datetime.now)
    total_pedidos = Column(Integer, default=0)
    total_gastado = Column(Float, default=0.0)
    ultima_visita = Column(DateTime)
    es_frecuente = Column(Boolean, default=False)


def generate_phone() -> str:
    return f"55{random.randint(1000, 9999)}{random.randint(1000, 9999)}"


def generate_email(nombre: str, apellido: str) -> str:
    dominios = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "protonmail.com"]
    base = f"{nombre.lower()}.{apellido.lower()}{random.randint(1, 999)}"
    return f"{base}@{random.choice(dominios)}"


def generate_address() -> tuple:
    calle = random.choice(CALLES)
    numero = random.randint(1, 999)
    colonia = random.choice(COLONIAS)
    idx = random.randint(0, len(CIUDADES) - 1)
    return f"{calle} {numero}", colonia, CIUDADES[idx], ESTADOS[idx], f"{random.randint(1000, 99999):05d}"


def calculate_price(base_price: float, tamaño: str, extras_list: list) -> tuple:
    mult = TAMAÑO_MULT[tamaño]
    subtotal = base_price * mult
    extras_total = sum(EXTRAS_DICT.get(e, 0) * mult for e in extras_list)
    subtotal += extras_total
    
    descuento = 0.0
    if random.random() < 0.15:
        descuento = round(subtotal * random.choice([0.1, 0.15, 0.2]), 2)
    
    total = round(subtotal - descuento, 2)
    return round(subtotal, 2), descuento, total


EXTRAS_DICT = dict(EXTRAS)


def create_engine_optimized():
    """Crea engine con configuración optimizada para bulk inserts"""
    return create_engine(
        DB_PATH,
        poolclass=NullPool,
        connect_args={
            "timeout": 30,
            "check_same_thread": False,
        },
        # PRAGMA optimizations para SQLite
        execution_options={
            "sqlite_fast_savepoints": True,
        }
    )


def apply_sqlite_pragmas(session):
    """Aplica pragmas de optimización SQLite"""
    pragmas = [
        "PRAGMA journal_mode = WAL",
        "PRAGMA synchronous = NORMAL",
        "PRAGMA cache_size = -32768",  # 32MB cache
        "PRAGMA temp_store = MEMORY",
        "PRAGMA mmap_size = 268435456",  # 256MB mmap
        "PRAGMA page_size = 4096",
    ]
    for pragma in pragmas:
        session.execute(text(pragma))
    session.commit()
    print("  ⚡ Pragmas SQLite optimizados aplicados")


def create_indexes(session):
    """Crea índices adicionales después de la carga masiva"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_pedidos_telefono_fecha ON pedidos(cliente_telefono, fecha_creacion DESC)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_ciudad_estado ON pedidos(ciudad, estado)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_total_fecha ON pedidos(total DESC, fecha_creacion DESC)",
    ]
    for idx in indexes:
        try:
            session.execute(text(idx))
        except Exception as e:
            print(f"  ⚠️ Índice ya existe o error: {e}")
    session.commit()
    print("  📇 Índices B-Tree creados/verificados")


def seed_pedidos(session, count: int, batch_size: int = 2000) -> int:
    """Siembra pedidos usando bulk insert optimizado"""
    print(f"🌱 Insertando {count:,} pedidos en lotes de {batch_size}...")
    
    start_time = time.time()
    inserted = 0
    
    # Preparar statements para bulk insert
    for batch_start in range(0, count, batch_size):
        batch_end = min(batch_start + batch_size, count)
        batch_count = batch_end - batch_start
        
        pedidos_data = []
        
        for _ in range(batch_count):
            # Cliente
            nombre = random.choice(NOMBRES)
            apellido = random.choice(APELLIDOS)
            telefono = generate_phone()
            email = generate_email(nombre, apellido) if random.random() > 0.3 else None
            
            direccion, colonia, ciudad, estado, cp = generate_address()
            
            # Pizza
            pizza_nombre, _, precio_base = random.choice(PIZZAS)
            tamaño = random.choice(TAMAÑOS)
            
            # Ingredientes quitados
            todos_ing = ["queso", "salsa de tomate", "pepperoni", "jamón", "piña",
                        "champiñones", "cebolla", "pimientos", "aceitunas", "bacon",
                        "rúcula", "parmesano", "alcachofas", "atún", "anchoas"]
            quitados = random.sample(todos_ing, random.randint(0, 2)) if random.random() > 0.7 else []
            
            # Extras
            extras_sel = random.sample(list(EXTRAS_DICT.keys()), random.randint(0, 3)) if random.random() > 0.5 else []
            
            # Precios
            subtotal, descuento, total = calculate_price(precio_base, tamaño, extras_sel)
            
            # Pago
            metodo_pago = random.choice(["efectivo", "mercadopago", "tarjeta", "transferencia"])
            estado_pago = "pagado" if random.random() > 0.1 else random.choice(["pendiente", "fallido"])
            
            # Estado pedido
            estado_pedido = random.choices(
                ["entregado", "listo", "horno", "preparando", "nuevo", "cancelado"],
                weights=[0.5, 0.1, 0.1, 0.1, 0.1, 0.1]
            )[0]
            
            # Fechas
            dias_atras = random.randint(0, 90)
            horas_atras = random.randint(0, 23)
            mins_atras = random.randint(0, 59)
            fecha = datetime.now() - timedelta(days=dias_atras, hours=horas_atras, minutes=mins_atras)
            
            pedidos_data.append({
                "cliente_nombre": f"{nombre} {apellido}",
                "cliente_telefono": telefono,
                "cliente_email": email,
                "direccion": direccion,
                "colonia": colonia,
                "ciudad": ciudad,
                "estado": estado,
                "codigo_postal": cp,
                "pizza_nombre": pizza_nombre,
                "tamaño": tamaño,
                "ingredientes_quitados": ", ".join(quitados) if quitados else None,
                "extras": ", ".join(extras_sel) if extras_sel else None,
                "subtotal": subtotal,
                "descuento": descuento,
                "total": total,
                "metodo_pago": metodo_pago,
                "estado_pago": estado_pago,
                "estado_pedido": estado_pedido,
                "fecha_creacion": fecha,
                "fecha_actualizacion": fecha,
            })
        
        # Bulk insert usando execute con values
        session.execute(
            text("""
                INSERT INTO pedidos (
                    cliente_nombre, cliente_telefono, cliente_email, direccion, colonia,
                    ciudad, estado, codigo_postal, pizza_nombre, tamaño, ingredientes_quitados,
                    extras, subtotal, descuento, total, metodo_pago, estado_pago, estado_pedido,
                    fecha_creacion, fecha_actualizacion
                ) VALUES (
                    :cliente_nombre, :cliente_telefono, :cliente_email, :direccion, :colonia,
                    :ciudad, :estado, :codigo_postal, :pizza_nombre, :tamaño, :ingredientes_quitados,
                    :extras, :subtotal, :descuento, :total, :metodo_pago, :estado_pago, :estado_pedido,
                    :fecha_creacion, :fecha_actualizacion
                )
            """),
            pedidos_data
        )
        session.commit()
        
        inserted += batch_count
        elapsed = time.time() - start_time
        rate = inserted / elapsed if elapsed > 0 else 0
        print(f"  📦 Lote {batch_start//batch_size + 1}: {inserted:,}/{count:,} ({rate:.0f} reg/s)")
    
    return inserted


def seed_clientes(session) -> int:
    """Crea tabla de clientes agregando desde pedidos"""
    print("👥 Generando tabla de clientes desde pedidos...")
    
    # Obtener stats por teléfono
    result = session.execute(text("""
        SELECT 
            cliente_telefono,
            MAX(cliente_nombre) as nombre,
            MAX(cliente_email) as email,
            MAX(direccion) as direccion,
            MAX(colonia) as colonia,
            MAX(ciudad) as ciudad,
            MAX(estado) as estado,
            MAX(codigo_postal) as cp,
            COUNT(*) as total_pedidos,
            SUM(total) as total_gastado,
            MAX(fecha_creacion) as ultima_visita,
            MIN(fecha_creacion) as primera_visita
        FROM pedidos
        GROUP BY cliente_telefono
    """)).fetchall()
    
    clientes_data = []
    for row in result:
        cliente = Cliente(
            nombre=row.nombre,
            telefono=row.cliente_telefono,
            email=row.email,
            direccion=row.direccion,
            colonia=row.colonia,
            ciudad=row.ciudad,
            estado=row.estado,
            codigo_postal=row.cp,
            fecha_registro=row.primera_visita - timedelta(days=random.randint(30, 365)),
            total_pedidos=row.total_pedidos,
            total_gastado=round(row.total_gastado, 2),
            ultima_visita=row.ultima_visita,
            es_frecuente=row.total_pedidos >= 3,
        )
        clientes_data.append(cliente)
    
    session.bulk_save_objects(clientes_data)
    session.commit()
    print(f"  ✅ {len(clientes_data):,} clientes creados")
    return len(clientes_data)


def seed_chroma(count: int = 5000):
    """Siembra ChromaDB con documentos del menú + variaciones sintéticas"""
    print(f"🔮 Insertando {count:,} vectores en ChromaDB...")
    
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Limpiar colección existente
    try:
        client.delete_collection("pizzeria_menu")
        print("  🗑️ Colección anterior eliminada")
    except:
        pass
    
    # Crear colección con HNSW optimizado
    collection = client.create_collection(
        name="pizzeria_menu",
        metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
            "hnsw:M": 16,
            "hnsw:search_ef": 100,
        }
    )
    print("  📦 Colección creada con HNSW optimizado")
    
    # Cargar modelo de embeddings
    print(f"  🤖 Cargando modelo {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    
    documents = []
    metadatas = []
    ids = []
    
    # 1. Documentos base: pizzas, extras, promos
    for pizza_nombre, descripcion, precio in PIZZAS:
        for tamaño in TAMAÑOS:
            mult = TAMAÑO_MULT[tamaño]
            precio_t = round(precio * mult, 2)
            doc = f"Pizza {pizza_nombre} {tamaño}: {descripcion}. Precio: ${precio_t:.2f} MXN"
            documents.append(doc)
            metadatas.append({
                "tipo": "pizza", "nombre": pizza_nombre, "tamaño": tamaño, "precio": precio_t
            })
            ids.append(f"pizza_{pizza_nombre.lower().replace(' ', '_')}_{tamaño.lower()}")
    
    for extra, precio in EXTRAS:
        doc = f"Extra {extra}: ${precio:.2f} MXN por ingrediente adicional"
        documents.append(doc)
        metadatas.append({"tipo": "extra", "nombre": extra, "precio": precio})
        ids.append(f"extra_{extra.lower().replace(' ', '_')}")
    
    for promo_nombre, descripcion, _ in PROMOCIONES:
        doc = f"Promoción {promo_nombre}: {descripcion}"
        documents.append(doc)
        metadatas.append({"tipo": "promocion", "nombre": promo_nombre})
        ids.append(f"promo_{promo_nombre.lower().replace(' ', '_')}")
    
    # 2. Variaciones sintéticas para alcanzar count
    variaciones = [
        "¿Cuánto cuesta la {pizza} {tamaño}?",
        "Precio de {pizza} tamaño {tamaño}",
        "Quiero una {pizza} {tamaño} por favor",
        "Menú: {pizza} {tamaño} - ${precio:.2f}",
        "Ingredientes de la {pizza}: {descripcion}",
        "¿Tienen {pizza} en tamaño {tamaño}?",
        "Me gustaría ordenar {pizza} {tamaño}",
        "¿La {pizza} {tamaño} lleva {ingrediente}?",
    ]
    
    ingredientes_lista = ["queso", "pepperoni", "jamón", "piña", "champiñones", "cebolla", "pimientos", "aceitunas"]
    
    while len(documents) < count:
        pizza_nombre, descripcion, precio = random.choice(PIZZAS)
        tamaño = random.choice(TAMAÑOS)
        mult = TAMAÑO_MULT[tamaño]
        precio_t = round(precio * mult, 2)
        ingrediente = random.choice(ingredientes_lista)
        
        template = random.choice(variaciones)
        doc = template.format(
            pizza=pizza_nombre, 
            tamaño=tamaño, 
            precio=precio_t,
            descripcion=descripcion,
            ingrediente=ingrediente
        )
        
        documents.append(doc)
        metadatas.append({
            "tipo": "variacion_sintetica",
            "pizza": pizza_nombre,
            "tamaño": tamaño,
            "precio": precio_t,
        })
        ids.append(f"syn_{len(documents)}")
    
    # Generar embeddings en lotes
    print(f"  🧮 Generando embeddings para {len(documents):,} documentos...")
    batch_size = 256
    all_embeddings = []
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        embeddings = model.encode(batch, show_progress_bar=False, normalize_embeddings=True)
        all_embeddings.extend(embeddings.tolist())
        
        if (i // batch_size + 1) % 10 == 0:
            print(f"    📐 Lote {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
    
    # Insertar en ChromaDB
    print("  💾 Insertando en ChromaDB...")
    collection.add(
        documents=documents,
        embeddings=all_embeddings,
        metadatas=metadatas,
        ids=ids,
    )
    
    print(f"  ✅ {collection.count():,} vectores insertados en ChromaDB")
    return collection.count()


def verify_counts(session):
    """Verifica conteos finales"""
    print("\n📊 VERIFICACIÓN DE CONTEOS")
    print("=" * 40)
    
    # SQLite
    pedidos_count = session.execute(text("SELECT COUNT(*) FROM pedidos")).scalar()
    clientes_count = session.execute(text("SELECT COUNT(*) FROM clientes")).scalar()
    
    # Stats pedidos
    stats = session.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT cliente_telefono) as clientes_unicos,
            COUNT(DISTINCT pizza_nombre) as pizzas_diferentes,
            AVG(total) as ticket_promedio,
            SUM(total) as ingreso_total,
            MIN(fecha_creacion) as primer_pedido,
            MAX(fecha_creacion) as ultimo_pedido
        FROM pedidos
    """)).fetchone()
    
    print(f"📋 Pedidos: {pedidos_count:,}")
    print(f"👥 Clientes: {clientes_count:,}")
    print(f"📞 Clientes únicos en pedidos: {stats.clientes_unicos:,}")
    print(f"🍕 Pizzas diferentes: {stats.pizzas_diferentes}")
    print(f"💰 Ticket promedio: ${stats.ticket_promedio:.2f}")
    print(f"💵 Ingreso total simulado: ${stats.ingreso_total:,.2f}")
    print(f"📅 Rango: {stats.primer_pedido} → {stats.ultimo_pedido}")
    
    # ChromaDB
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False))
        coll = client.get_collection("pizzeria_menu")
        print(f"🔮 ChromaDB vectores: {coll.count():,}")
    except:
        print("🔮 ChromaDB: No disponible")
    
    # Verificar índices
    indexes = session.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pedidos'")).fetchall()
    print(f"📇 Índices en tabla pedidos: {len(indexes)}")
    for idx in indexes:
        print(f"   - {idx[0]}")
    
    # Nivel alcanzado
    if pedidos_count >= 50000:
        print("\n🏆 NIVEL: EXCELENTE (50,000+ registros)")
    elif pedidos_count >= 10000:
        print("\n✅ NIVEL: COMPETENTE (10,000+ registros)")
    else:
        print(f"\n⚠️ NIVEL: INSUFICIENTE ({pedidos_count:,}/10,000 mínimo)")
    
    return pedidos_count


def main():
    parser = argparse.ArgumentParser(description="Sembrado de datos Semana 7")
    parser.add_argument("--full", action="store_true", help="50,000 registros (Nivel Excelente)")
    parser.add_argument("--count", type=int, default=None, help="Número personalizado de registros")
    parser.add_argument("--verify", action="store_true", help="Solo verificar conteos")
    parser.add_argument("--skip-chroma", action="store_true", help="Omitir ChromaDB")
    args = parser.parse_args()
    
    target_count = args.count or (50000 if args.full else 10000)
    chroma_count = max(5000, target_count // 2)
    
    print("=" * 60)
    print("🌱 SEMBRADO DE DATOS DE ESTRÉS - SEMANA 7")
    print("=" * 60)
    print(f"Objetivo: {target_count:,} pedidos SQLite + {chroma_count:,} vectores ChromaDB")
    
    if args.verify:
        engine = create_engine_optimized()
        Session = sessionmaker(bind=engine)
        session = Session()
        verify_counts(session)
        return
    
    # Crear engine y sesión
    engine = create_engine_optimized()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Aplicar optimizaciones SQLite
        apply_sqlite_pragmas(session)
        
        # 1. Sembrar pedidos (bulk insert)
        print(f"\n1️⃣ SEMILLANDO {target_count:,} PEDIDOS")
        t0 = time.time()
        seed_pedidos(session, target_count)
        t1 = time.time()
        print(f"   ⏱️  Tiempo: {t1-t0:.1f}s ({(t1-t0)/target_count*1000:.2f} ms/reg)")
        
        # 2. Crear índices
        print("\n2️⃣ CREANDO ÍNDICES B-TREE")
        create_indexes(session)
        
        # 3. Generar clientes agregados
        print("\n3️⃣ GENERANDO TABLA CLIENTES")
        seed_clientes(session)
        
        # 4. Sembrar ChromaDB
        if not args.skip_chroma:
            print("\n4️⃣ SEMILLANDO CHROMADB (HNSW)")
            t0 = time.time()
            seed_chroma(chroma_count)
            t1 = time.time()
            print(f"   ⏱️  Tiempo: {t1-t0:.1f}s")
        else:
            print("\n4️⃣ ChromaDB omitido (--skip-chroma)")
        
        # 5. Verificar
        print("\n5️⃣ VERIFICACIÓN FINAL")
        verify_counts(session)
        
        print("\n" + "=" * 60)
        print("✅ SEMBRADO COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()