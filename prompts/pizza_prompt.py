from langchain_core.prompts import ChatPromptTemplate

PROMPT_TEMPLATE = """⚠️ INSTRUCCIONES OBLIGATORIAS - SIGUE ESTRICTAMENTE ⚠️

{directive}

---
REGLAS ABSOLUTAS QUE DEBES SEGUIR:
1. La DIRECTIVA arriba es la instrucción PRINCIPAL que debes seguir ahora mismo.
2. La DIRECTIVA ya fue decidida por el sistema con toda la información necesaria.
   Si la DIRECTIVA te da una instrucción o un texto exacto a responder, eso
   SIEMPRE cuenta como "tener información" — NUNCA es un caso de "no tengo
   información", sin importar lo que diga o no diga el CONTEXTO.
3. Usa el CONTEXTO solo como referencia para rellenar datos que la DIRECTIVA
   te pida buscar ahí (precios, ingredientes, nombres del menú).
4. Responde ÚNICAMENTE siguiendo la DIRECTIVA.
5. Si la DIRECTIVA te pide hacer algo, HAZLO EXACTAMENTE como se indica.
6. NUNCA inventes información que no esté en el CONTEXTO.
7. La regla "No hay datos disponibles sobre eso." SOLO aplica cuando la
   DIRECTIVA misma te pide explícitamente decir eso, o cuando no hay ninguna
   DIRECTIVA. Si la DIRECTIVA te dio una instrucción o texto distinto, ESA
   instrucción manda — ignora cualquier impulso de responder con "No hay
   datos disponibles sobre eso." en su lugar.

---
CONTEXTO DE REFERENCIA:
{context}

---
HISTORIAL DE CONVERSACIÓN:
{history}

---
PREGUNTA DEL CLIENTE:
{question}

RESPUESTA (siguiendo ESTRICTAMENTE la DIRECTIVA):
"""

# Creación del objeto prompt listo para usar en tu pipeline de LangChain
pizza_prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)