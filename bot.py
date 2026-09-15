import os
import discord
from openai import OpenAI

# ==============================
# CONFIGURACIÓN
# ==============================

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

# Cliente de OpenRouter
ai = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# ==============================
# DISCORD
# ==============================

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# ==============================
# CUANDO EL BOT SE CONECTA
# ==============================

@bot.event
async def on_ready():
    print(f"AbelAI conectado como {bot.user}")
    print("El bot está listo para recibir preguntas.")

# ==============================
# MENSAJES
# ==============================

@bot.event
async def on_message(message):

    # Ignorar mensajes del propio bot
    if message.author == bot.user:
        return

    # Solo responder a ?ai
    if not message.content.lower().startswith("?ai"):
        return

    # Obtener la pregunta
    pregunta = message.content[3:].strip()

    # Si no escribió ninguna pregunta
    if not pregunta:
        await message.reply(
            "🤖 Escribe una pregunta después de `?ai`.\n\n"
            "Ejemplo: `?ai ¿Cuál es la capital de España?`"
        )
        return

    # Avisar de que está pensando
    async with message.channel.typing():

        try:

            respuesta = ai.chat.completions.create(
                model="openrouter/free",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu nombre es AbelAI. "
                            "Eres un asistente de inteligencia artificial "
                            "amable, útil y divertido. "
                            "Responde principalmente en español. "
                            "Si el usuario habla en otro idioma, "
                            "puedes responder en ese idioma. "
                            "Da respuestas claras y fáciles de entender."
                        )
                    },
                    {
                        "role": "user",
                        "content": pregunta
                    }
                ]
            )

            texto = respuesta.choices[0].message.content

            # Discord permite mensajes de hasta 2000 caracteres.
            if len(texto) <= 2000:
                await message.reply(texto)
            else:
                # Dividir respuestas demasiado largas
                for i in range(0, len(texto), 2000):
                    await message.channel.send(texto[i:i + 2000])

        except Exception as error:

            print("ERROR:", error)

            await message.reply(
                "❌ Ha ocurrido un error al hablar con la IA. "
                "Inténtalo de nuevo en unos segundos."
            )


# ==============================
# INICIAR BOT
# ==============================

bot.run(DISCORD_TOKEN)
