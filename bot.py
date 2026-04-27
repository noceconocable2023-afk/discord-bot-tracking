import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

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
# CONFIG & TIMEZONE (UTC-5)
# =========================
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1493618366093459669  # tu servidor
GUILD = discord.Object(id=GUILD_ID)

def get_lima_time():
    # Render usa UTC, restamos 5 horas para Lima
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%d/%m/%Y %H:%M:%S")

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

# =========================
# DATA MANAGEMENT
# =========================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# =========================
# READY (SYNC)
# =========================
@bot.event
async def on_ready():
    # Limpiamos y sincronizamos comandos para el gremio específico
    bot.tree.clear_commands(guild=GUILD)
    await bot.tree.sync(guild=GUILD)
    print(f"Bot conectado como {bot.user} | Zona Horaria: Lima UTC-5")
    await bot.change_presence(activity=discord.Game(name="/help"))

# =========================
# COMANDO: HELP
# =========================
@bot.tree.command(name="help", description="Ver lista de comandos disponibles", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    mensaje = (
        "📦 **SISTEMA DE GESTIÓN DE REQUERIMIENTOS**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "**/crear** [codigo] [estado] → Registra un nuevo requerimiento.\n"
        "**/ver** [codigo] → Consulta historial y fechas.\n"
        "**/actualizar** [codigo] [nuevo_estado] → Cambia el estado actual.\n"
        "**/lista** [tipo] → Filtra por abiertos, cerrados o todos.\n"
        "**/cerrar** [codigo] → Finaliza un requerimiento permanentemente."
    )
    await interaction.response.send_message(mensaje)

# =========================
# COMANDO: CREAR
# =========================
@bot.tree.command(name="crear", description="Crear un nuevo requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código identificador", estado="Estado inicial del requerimiento")
async def crear(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo in data:
        await interaction.response.send_message(f"❌ El código **{codigo}** ya existe.", ephemeral=True)
        return

    ahora = get_lima_time()
    data[codigo] = {
        "estado": estado,
        "creado_el": ahora,
        "actualizado_el": ahora,
        "cerrado": False,
        "cerrado_el": None,
        "historial": [f"Creado con estado: {estado} ({ahora})"]
    }
    save_data(data)
    await interaction.response.send_message(f"✅ Requerimiento **{codigo}** creado correctamente a las {ahora}.")

# =========================
# COMANDO: VER
# =========================
@bot.tree.command(name="ver", description="Consultar detalles de un requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código a buscar")
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        await interaction.response.send_message(f"❌ No se encontró el código **{codigo}**.", ephemeral=True)
        return

    info = data[codigo]
    historial_str = "\n".join([f"• {h}" for h in info["historial"]])
    color_status = "🟢 ABIERTO" if not info["cerrado"] else f"🔴 CERRADO ({info['cerrado_el']})"

    mensaje = (
        f"📋 **DETALLES DEL REQUERIMIENTO: {codigo}**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"**Estado Actual:** {info['estado']}\n"
        f"**Disponibilidad:** {color_status}\n"
        f"**Fecha de Creación:** {info['creado_el']}\n"
        f"**Última Actualización:** {info['actualizado_el']}\n\n"
        f"**Línea de Tiempo:**\n{historial_str}"
    )
    await interaction.response.send_message(mensaje)

# =========================
# COMANDO: ACTUALIZAR
# =========================
@bot.tree.command(name="actualizar", description="Actualizar el estado de un requerimiento", guild=GUILD)
@app_commands.describe(codigo="Código", estado="Nuevo estado")
async def actualizar(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo not in data:
        await interaction.response.send_message("❌ El código no existe.", ephemeral=True)
        return
    if data[codigo].get("cerrado"):
        await interaction.response.send_message("🔒 No se puede actualizar un requerimiento cerrado.", ephemeral=True)
        return

    ahora = get_lima_time()
    data[codigo]["estado"] = estado
    data[codigo]["actualizado_el"] = ahora
    data[codigo]["historial"].append(f"Cambio a: {estado} ({ahora})")
    
    save_data(data)
    await interaction.response.send_message(f"🔄 **{codigo}** actualizado a: **{estado}**.")

# =========================
# COMANDO: LISTA
# =========================
@bot.tree.command(name="lista", description="Listar requerimientos", guild=GUILD)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Abiertos", value="abiertos"),
    app_commands.Choice(name="Cerrados", value="cerrados"),
    app_commands.Choice(name="Todos", value="todos")
])
async def lista(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    data = load_data()
    resultado = []
    
    for codigo, info in data.items():
        es_cerrado = info.get("cerrado", False)
        if tipo.value == "abiertos" and not es_cerrado:
            resultado.append(f"🟢 `{codigo}`: {info['estado']}")
        elif tipo.value == "cerrados" and es_cerrado:
            resultado.append(f"🔴 `{codigo}`: {info['estado']}")
        elif tipo.value == "todos":
            icon = "🔴" if es_cerrado else "🟢"
            resultado.append(f"{icon} `{codigo}`: {info['estado']}")

    if not resultado:
        await interaction.response.send_message(f"📭 No hay requerimientos en la categoría: **{tipo.name}**.")
        return

    # Discord tiene un límite de 2000 caracteres, enviamos los primeros 20
    mensaje_final = "\n".join(resultado[:20])
    await interaction.response.send_message(f"📋 **Lista de Requerimientos ({tipo.name}):**\n{mensaje_final}")

# =========================
# VISTA: CONFIRMAR CIERRE
# =========================
class ConfirmarCerrar(discord.ui.View):
    def __init__(self, codigo):
        super().__init__(timeout=30)
        self.codigo = codigo

    @discord.ui.button(label="Confirmar Cierre", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        if self.codigo in data:
            ahora = get_lima_time()
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            data[self.codigo]["historial"].append(f"REQUERIMIENTO CERRADO ({ahora})")
            save_data(data)
            await interaction.response.edit_message(content=f"🔒 El requerimiento **{self.codigo}** ha sido cerrado el {ahora}.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Acción cancelada.", view=None)

# =========================
# COMANDO: CERRAR
# =========================
@bot.tree.command(name="cerrar", description="Cerrar un requerimiento definitivamente", guild=GUILD)
@app_commands.describe(codigo="Código a cerrar")
async def cerrar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        await interaction.response.send_message("❌ No existe el código.", ephemeral=True)
        return
    if data[codigo].get("cerrado"):
        await interaction.response.send_message("⚠️ Este requerimiento ya se encuentra cerrado.", ephemeral=True)
        return

    view = ConfirmarCerrar(codigo)
    await interaction.response.send_message(f"⚠️ ¿Estás seguro que deseas cerrar **{codigo}**? Esta acción no se puede deshacer.", view=view)

# =========================
# EJECUCIÓN
# =========================
bot.run(TOKEN)
