import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread

# =========================
# KEEP ALIVE (Render)
# =========================
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
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1493618366093459669  # tu servidor
GUILD = discord.Object(id=GUILD_ID)

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

# =========================
# DATA
# =========================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =========================
# READY (ANTI DUPLICADOS)
# =========================
@bot.event
async def on_ready():
    bot.tree.clear_commands(guild=None)
    bot.tree.clear_commands(guild=GUILD)

    await bot.tree.sync(guild=GUILD)

    print(f"Bot conectado como {bot.user}")

    await bot.change_presence(
        activity=discord.Game(name="/help")
    )

# =========================
# HELP
# =========================
@bot.tree.command(name="help", description="Ver comandos", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    mensaje = """
📦 **COMANDOS DISPONIBLES**

/crear → Crear requerimiento  
/ver → Ver estado  
/actualizar → Actualizar estado  
/lista → Ver requerimientos  
/cerrar → Cerrar requerimiento  
    """
    await interaction.response.send_message(mensaje)

# =========================
# CREAR
# =========================
@bot.tree.command(name="crear", description="Crear requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código", estado="Estado inicial")
async def crear(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()

    if codigo in data:
        await interaction.response.send_message("❌ Ya existe ese código")
        return

    data[codigo] = {
        "estado": estado,
        "historial": [estado],
        "cerrado": False
    }

    save_data(data)

    await interaction.response.send_message(f"✅ {codigo} creado con estado: {estado}")

# =========================
# VER
# =========================
@bot.tree.command(name="ver", description="Ver estado", guild=GUILD)
@app_commands.describe(codigo="Código")
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo not in data:
        await interaction.response.send_message("❌ No existe")
        return

    info = data[codigo]
    estado = info["estado"]
    historial = " → ".join(info["historial"])
    cerrado = "🔒 Cerrado" if info.get("cerrado") else "🟢 Abierto"

    await interaction.response.send_message(
        f"📦 {codigo}\nEstado: {estado}\nHistorial: {historial}\n{cerrado}"
    )

# =========================
# ACTUALIZAR
# =========================
@bot.tree.command(name="actualizar", description="Actualizar estado", guild=GUILD)
@app_commands.describe(codigo="Código", estado="Nuevo estado")
async def actualizar(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()

    if codigo not in data:
        await interaction.response.send_message("❌ No existe")
        return

    if data[codigo].get("cerrado"):
        await interaction.response.send_message("🔒 Está cerrado")
        return

    data[codigo]["estado"] = estado
    data[codigo]["historial"].append(estado)

    save_data(data)

    await interaction.response.send_message(f"🔄 {codigo} actualizado: {estado}")

# =========================
# LISTA
# =========================
@bot.tree.command(name="lista", description="Ver requerimientos", guild=GUILD)
@app_commands.describe(tipo="abiertos, cerrados o todos")
async def lista(interaction: discord.Interaction, tipo: str):
    data = load_data()
    tipo = tipo.lower()

    resultado = []

    for codigo, info in data.items():
        cerrado = info.get("cerrado", False)

        if tipo == "abiertos" and not cerrado:
            resultado.append(f"🟢 {codigo} → {info['estado']}")
        elif tipo == "cerrados" and cerrado:
            resultado.append(f"🔴 {codigo} → {info['estado']}")
        elif tipo == "todos":
            icono = "🔴" if cerrado else "🟢"
            resultado.append(f"{icono} {codigo} → {info['estado']}")

    if not resultado:
        await interaction.response.send_message("📭 No hay datos")
        return

    mensaje = "\n".join(resultado[:20])

    await interaction.response.send_message(f"📋 Lista:\n{mensaje}")

# =========================
# CONFIRMAR CIERRE
# =========================
class ConfirmarCerrar(discord.ui.View):
    def __init__(self, codigo):
        super().__init__(timeout=30)
        self.codigo = codigo

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()

        if self.codigo not in data:
            await interaction.response.send_message("❌ No existe", ephemeral=True)
            return

        data[self.codigo]["cerrado"] = True
        save_data(data)

        await interaction.response.edit_message(content=f"🔒 {self.codigo} cerrado", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Cancelado", view=None)

# =========================
# CERRAR
# =========================
@bot.tree.command(name="cerrar", description="Cerrar requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código")
async def cerrar(interaction: discord.Interaction, codigo: str):
    data = load_data()

    if codigo not in data:
        await interaction.response.send_message("❌ No existe")
        return

    if data[codigo].get("cerrado"):
        await interaction.response.send_message("⚠️ Ya está cerrado")
        return

    view = ConfirmarCerrar(codigo)

    await interaction.response.send_message(
        f"⚠️ ¿Seguro que quieres cerrar {codigo}?",
        view=view
    )

# =========================
# RUN
# =========================
bot.run(TOKEN)
