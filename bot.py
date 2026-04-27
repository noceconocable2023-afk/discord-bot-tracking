import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# =========================
# GUILD ID (TU SERVIDOR)
# =========================
GUILD_ID = 1493618366093459669
GUILD = discord.Object(id=GUILD_ID)

# =========================
# KEEP ALIVE (Render)
# =========================
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# =========================
# CONFIG DISCORD
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA
# =========================
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    # ❌ BORRAR comandos globales
    bot.tree.clear_commands(guild=None)

    # ✅ SINCRONIZAR solo en tu servidor
    await bot.tree.sync(guild=GUILD)

    print(f"Bot conectado como {bot.user}")

    await bot.change_presence(
        activity=discord.Game(name="/help")
    )

# =========================
# VISTAS (BOTONES)
# =========================

class ConfirmarEliminar(discord.ui.View):
    def __init__(self, codigo, user_id):
        super().__init__(timeout=30)
        self.codigo = codigo
        self.user_id = user_id

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No puedes usar esta acción", ephemeral=True)
            return

        data = load_data()

        if self.codigo in data:
            del data[self.codigo]
            save_data(data)

            await interaction.response.edit_message(
                content=f"🗑️ **{self.codigo} eliminado correctamente**",
                view=None
            )
        else:
            await interaction.response.edit_message(
                content="❌ Ya no existe ese requerimiento",
                view=None
            )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❎ Eliminación cancelada",
            view=None
        )


class ConfirmarRetroceder(discord.ui.View):
    def __init__(self, codigo, user_id):
        super().__init__(timeout=30)
        self.codigo = codigo
        self.user_id = user_id

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No puedes usar esta acción", ephemeral=True)
            return

        data = load_data()

        if self.codigo in data:
            if len(data[self.codigo]["historial"]) > 1:
                data[self.codigo]["historial"].pop()
                data[self.codigo]["estado"] = data[self.codigo]["historial"][-1]
                save_data(data)

                await interaction.response.edit_message(
                    content=f"↩️ **{self.codigo} retrocedido**\nEstado: {data[self.codigo]['estado']}",
                    view=None
                )
            else:
                await interaction.response.edit_message(
                    content="⚠️ No puedes retroceder más",
                    view=None
                )
        else:
            await interaction.response.edit_message(
                content="❌ No existe ese requerimiento",
                view=None
            )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❎ Operación cancelada",
            view=None
        )

# =========================
# COMANDOS SLASH (INSTANT)
# =========================

@bot.tree.command(name="help", description="Ver comandos", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📖 **Comandos disponibles:**\n\n"
        "🔹 /crear\n"
        "🔹 /estado\n"
        "🔹 /actualizar\n"
        "🔹 /historial\n"
        "🔹 /retroceder\n"
        "🔹 /eliminar\n"
    )

@bot.tree.command(name="crear", description="Crear requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código", estado="Estado inicial")
async def crear(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    data[codigo] = {"estado": estado, "historial": [estado]}
    save_data(data)

    await interaction.response.send_message(f"✅ {codigo} creado\nEstado: {estado}")

@bot.tree.command(name="estado", description="Consultar estado", guild=GUILD)
@app_commands.describe(codigo="Código")
async def estado(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo in data:
        await interaction.response.send_message(f"📦 {codigo}\nEstado: {data[codigo]['estado']}")
    else:
        await interaction.response.send_message("❌ No existe ese requerimiento")

@bot.tree.command(name="actualizar", description="Actualizar estado", guild=GUILD)
@app_commands.describe(codigo="Código", nuevo_estado="Nuevo estado")
async def actualizar(interaction: discord.Interaction, codigo: str, nuevo_estado: str):
    data = load_data()

    if codigo in data:
        data[codigo]["estado"] = nuevo_estado
        data[codigo]["historial"].append(nuevo_estado)
        save_data(data)

        await interaction.response.send_message(f"🔄 {codigo} actualizado\nEstado: {nuevo_estado}")
    else:
        await interaction.response.send_message("❌ No existe ese requerimiento")

@bot.tree.command(name="historial", description="Ver historial", guild=GUILD)
@app_commands.describe(codigo="Código")
async def historial(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo in data:
        historial = "\n- ".join(data[codigo]["historial"])
        await interaction.response.send_message(f"📜 Historial de {codigo}:\n- {historial}")
    else:
        await interaction.response.send_message("❌ No existe ese requerimiento")

@bot.tree.command(name="retroceder", description="Eliminar último estado", guild=GUILD)
@app_commands.describe(codigo="Código")
async def retroceder(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo not in data:
        await interaction.response.send_message("❌ No existe ese requerimiento")
        return

    view = ConfirmarRetroceder(codigo, interaction.user.id)

    await interaction.response.send_message(
        f"⚠️ ¿Deseas retroceder **{codigo}**?",
        view=view
    )

@bot.tree.command(name="eliminar", description="Eliminar requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código")
async def eliminar(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo not in data:
        await interaction.response.send_message("❌ No existe ese requerimiento")
        return

    view = ConfirmarEliminar(codigo, interaction.user.id)

    await interaction.response.send_message(
        f"⚠️ ¿Eliminar **{codigo}**?",
        view=view
    )

# =========================
# RUN
# =========================
bot.run(os.getenv("TOKEN"))
