import os
import asyncio
import sqlite3
import re
from datetime import timedelta

import discord
from openai import OpenAI


# =========================================================
# CONFIGURACIÓN
# =========================================================

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

CREADOR = "Abel997899"
MAX_MEMORY = 10


# =========================================================
# OPENROUTER
# =========================================================

ai = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)


# =========================================================
# BASE DE DATOS
# =========================================================

db = sqlite3.connect("abelai_memory.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    fact_value TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# MEMORIA
# =========================================================

def save_message(user_id, role, content):
    cursor.execute(
        """
        INSERT INTO messages (user_id, role, content)
        VALUES (?, ?, ?)
        """,
        (str(user_id), role, content)
    )

    cursor.execute(
        """
        SELECT id
        FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT -1 OFFSET ?
        """,
        (str(user_id), MAX_MEMORY)
    )

    old_messages = cursor.fetchall()

    for row in old_messages:
        cursor.execute(
            "DELETE FROM messages WHERE id = ?",
            (row[0],)
        )

    db.commit()


def get_memory(user_id):
    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ?
        ORDER BY id ASC
        """,
        (str(user_id),)
    )

    return cursor.fetchall()


def save_fact(user_id, fact_type, fact_value):
    cursor.execute(
        """
        DELETE FROM user_facts
        WHERE user_id = ? AND fact_type = ?
        """,
        (str(user_id), fact_type)
    )

    cursor.execute(
        """
        INSERT INTO user_facts
        (user_id, fact_type, fact_value)
        VALUES (?, ?, ?)
        """,
        (str(user_id), fact_type, fact_value)
    )

    db.commit()


def get_facts(user_id):
    cursor.execute(
        """
        SELECT fact_type, fact_value
        FROM user_facts
        WHERE user_id = ?
        """,
        (str(user_id),)
    )

    return cursor.fetchall()


def clear_memory(user_id):
    cursor.execute(
        "DELETE FROM messages WHERE user_id = ?",
        (str(user_id),)
    )

    cursor.execute(
        "DELETE FROM user_facts WHERE user_id = ?",
        (str(user_id),)
    )

    db.commit()


# =========================================================
# DETECTAR NOMBRE
# =========================================================

def detect_name(text):
    patterns = [
        r"\bme llamo\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)",
        r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)",
        r"\bsoy\s+([A-Za-zÁÉÍÓÚáéíóúÑñ0-9_.-]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1)

    return None


# =========================================================
# ANTI @
# =========================================================

def remove_mentions(text):
    return text.replace("@", "")


# =========================================================
# DETECTAR INSULTOS
# =========================================================

async def detect_insult(text):

    try:

        resultado = await asyncio.to_thread(
            ai.chat.completions.create,

            model="openrouter/free",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un moderador de Discord. "
                        "Analiza únicamente si el mensaje contiene "
                        "un insulto dirigido a otra persona. "
                        "No consideres insulto una conversación normal, "
                        "una palabra usada de forma amistosa o una "
                        "simple opinión. "
                        "Responde ÚNICAMENTE con una palabra: "
                        "SI o NO."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        decision = resultado.choices[0].message.content

        if not decision:
            return False

        decision = decision.strip().upper()

        return decision.startswith("SI")

    except Exception as error:

        print(
            f"⚠️ Error detectando insulto: {error}"
        )

        return False


# =========================================================
# DETECTAR PREGUNTAS SOBRE EL CREADOR
# =========================================================

def pregunta_sobre_creador(texto):

    texto = texto.lower()

    palabras = [

        "quien es el creador",
        "quién es el creador",

        "quien creó la ia",
        "quién creó la ia",

        "quien creo la ia",
        "quién creo la ia",

        "quien hizo la ia",
        "quién hizo la ia",

        "quien te creo",
        "quién te creó",

        "quien te ha creado",
        "quién te ha creado",

        "quien te hizo",
        "quién te hizo",

        "creador de la ia",
        "creador de abelai",

        "dueño de la ia",
        "dueño de abelai",

        "autor de la ia",
        "autor de abelai",

        "quien hizo abelai",
        "quién hizo abelai",

        "quien creo abelai",
        "quién creó abelai",

        "quien creó abelai",
        "quién creo abelai"
    ]

    return any(
        palabra in texto
        for palabra in palabras
    )


# =========================================================
# DISCORD
# =========================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True

bot = discord.Client(
    intents=intents
)


# =========================================================
# BOT LISTO
# =========================================================

@bot.event
async def on_ready():

    print()
    print("🚀 Iniciando AbelAI...")
    print("🧠 Sistema de memoria cargado...")
    print("🚫 Sistema anti-@ cargado...")
    print("🛡️ Sistema de moderación cargado...")
    print("⏱️ Timeout configurado: 1 hora")
    print("⚡ Sistema anti-bloqueo cargado...")
    print()
    print(f"🤖 Conectado como: {bot.user}")
    print(f"🆔 ID del bot: {bot.user.id}")
    print()


# =========================================================
# MENSAJES
# =========================================================

@bot.event
async def on_message(message):

    # -----------------------------------------------------
    # IGNORAR BOTS
    # -----------------------------------------------------

    if message.author.bot:
        return


    # -----------------------------------------------------
    # MODERACIÓN AUTOMÁTICA
    # -----------------------------------------------------

    es_insulto = await detect_insult(
        message.content
    )

    if es_insulto:

        print(
            f"🚨 Insulto detectado de "
            f"{message.author}: {message.content}"
        )

        miembro = message.author

        if isinstance(
            miembro,
            discord.Member
        ):

            # ---------------------------------------------
            # NO TIMEOUT AL DUEÑO DEL SERVIDOR
            # ---------------------------------------------

            if (
                message.guild
                and message.guild.owner_id
                == miembro.id
            ):

                print(
                    "⚠️ El usuario es el dueño "
                    "del servidor. No se aplica timeout."
                )

            else:

                try:

                    # -------------------------------------
                    # COMPROBAR JERARQUÍA
                    # -------------------------------------

                    if (
                        message.guild
                        and message.guild.me
                        and miembro.top_role
                        >= message.guild.me.top_role
                    ):

                        print(
                            "⚠️ No puedo aplicar timeout "
                            "porque el usuario tiene "
                            "un rol igual o superior al mío."
                        )

                    else:

                        await miembro.timeout(
                            timedelta(hours=1),
                            reason=(
                                "Insulto detectado "
                                "por AbelAI"
                            )
                        )

                        print(
                            f"⏱️ Timeout de 1 hora aplicado "
                            f"a {miembro}"
                        )

                        await message.channel.send(
                            "🛡️ Has recibido un timeout "
                            "de 1 hora por insultar.",
                            allowed_mentions=(
                                discord.AllowedMentions.none()
                            )
                        )

                        return

                except discord.Forbidden:

                    print(
                        "❌ No tengo permisos para "
                        "aplicar timeout."
                    )

                except discord.HTTPException as error:

                    print(
                        f"❌ Error de Discord: {error}"
                    )


    # -----------------------------------------------------
    # PREGUNTA SOBRE EL CREADOR
    # -----------------------------------------------------

    if pregunta_sobre_creador(
        message.content
    ):

        await message.channel.send(
            f"El creador de esta IA es {CREADOR}.",
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )

        return


    # -----------------------------------------------------
    # COMANDO CLEAR
    # -----------------------------------------------------

    if message.content.lower().strip() == "?clear":

        clear_memory(
            message.author.id
        )

        await message.channel.send(
            "🗑️ Tu memoria ha sido borrada.",
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )

        return


    # -----------------------------------------------------
    # COMANDO ?AI
    # -----------------------------------------------------

    if not message.content.lower().startswith("?ai"):

        return


    pregunta = message.content[3:].strip()


    # -----------------------------------------------------
    # COMPROBAR PREGUNTA VACÍA
    # -----------------------------------------------------

    if not pregunta:

        await message.channel.send(
            "🤖 Escribe una pregunta después de `?ai`.",
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )

        return


    # -----------------------------------------------------
    # DETECTAR NOMBRE
    # -----------------------------------------------------

    nombre = detect_name(
        pregunta
    )

    if nombre:

        save_fact(
            message.author.id,
            "nombre",
            nombre
        )

        print(
            f"🧠 Nombre guardado: "
            f"{message.author} → {nombre}"
        )


    # -----------------------------------------------------
    # OBTENER MEMORIA
    # -----------------------------------------------------

    memoria = get_memory(
        message.author.id
    )

    hechos = get_facts(
        message.author.id
    )


    # -----------------------------------------------------
    # CREAR CONTEXTO
    # -----------------------------------------------------

    contexto_memoria = []

    for role, content in memoria:

        contexto_memoria.append(
            {
                "role": role,
                "content": content
            }
        )


    # -----------------------------------------------------
    # HECHOS DEL USUARIO
    # -----------------------------------------------------

    datos_usuario = ""

    for fact_type, fact_value in hechos:

        if fact_type == "nombre":

            datos_usuario += (
                f"\nEl nombre del usuario es "
                f"{fact_value}."
            )


    # -----------------------------------------------------
    # GUARDAR MENSAJE
    # -----------------------------------------------------

    save_message(
        message.author.id,
        "user",
        pregunta
    )


    # -----------------------------------------------------
    # SYSTEM PROMPT
    # -----------------------------------------------------

    system_prompt = f"""
Eres AbelAI, una inteligencia artificial
que funciona dentro de Discord.

El creador de AbelAI es {CREADOR}.

Si el usuario pregunta quién es el creador,
quién hizo la IA, quién te creó o algo parecido,
responde siempre:

"El creador de esta IA es {CREADOR}."

IMPORTANTE:
- Responde en el mismo idioma que utiliza el usuario.
- Sé amable y natural.
- No hagas respuestas innecesariamente largas.
- Puedes usar emojis cuando sea apropiado.
- Nunca escribas menciones de Discord.
- Nunca uses el símbolo @.
- No intentes mencionar usuarios.
- Respeta la memoria individual de cada usuario.
- Nunca mezcles información de otros usuarios.

Información conocida sobre este usuario:
{datos_usuario}
"""


    # -----------------------------------------------------
    # MENSAJES PARA OPENROUTER
    # -----------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(
        contexto_memoria
    )

    messages.append(
        {
            "role": "user",
            "content": pregunta
        }
    )


    # -----------------------------------------------------
    # INDICADOR
    # -----------------------------------------------------

    try:

        async with message.channel.typing():

            respuesta = await asyncio.to_thread(

                ai.chat.completions.create,

                model="openrouter/free",

                messages=messages
            )


        # -------------------------------------------------
        # OBTENER RESPUESTA
        # -------------------------------------------------

        texto = (
            respuesta
            .choices[0]
            .message
            .content
        )


        if not texto:

            texto = (
                "❌ No he recibido una respuesta "
                "del modelo."
            )


        # -------------------------------------------------
        # ANTI @
        # -------------------------------------------------

        texto = remove_mentions(
            texto
        )


        # -------------------------------------------------
        # GUARDAR RESPUESTA
        # -------------------------------------------------

        save_message(
            message.author.id,
            "assistant",
            texto
        )


        # -------------------------------------------------
        # ENVIAR RESPUESTA
        # -------------------------------------------------

        await message.channel.send(
            texto,
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )


    except Exception as error:

        print(
            f"❌ Error con OpenRouter: {error}"
        )

        await message.channel.send(
            "❌ Ha ocurrido un error al hablar "
            "con la IA.",
            allowed_mentions=(
                discord.AllowedMentions.none()
            )
        )


# =========================================================
# INICIAR BOT
# =========================================================

bot.run(
    DISCORD_TOKEN
)