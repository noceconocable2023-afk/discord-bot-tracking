import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# ==========================================
# CONFIGURACIÓN DE FLASK (Keep Alive Render)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Servidor del Bot encendido"

def run_flask():
    # Render asigna el puerto automáticamente en la variable PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True # Esto asegura que el hilo se cierre si el bot se apaga
    t.start()

# ==========================================
# CONFIGURACIÓN DEL BOT Y ZONA HORARIA
# ==========================================
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1493618366093459669  # Tu ID de servidor
GUILD = discord.Object(id=GUILD_ID)

def get_lima_time():
    # Ajuste manual para UTC-5 (America/Lima)
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%d/%m/%Y %H:%M:%S")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

# ==========================================
# GESTIÓN DE DATOS (JSON)
# ==========================================
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

# ==========================================
# EVENTOS INICIALES
# ==========================================
@bot.event
async def on_ready():
    # Sincronizamos comandos solo con tu servidor para que sea instantáneo
    await bot.tree.sync(guild=GUILD)
    print(f"✅ Conectado como: {bot.user}")
    print(f"📅 Hora Lima: {get_lima_time()}")
    await bot.change_presence(activity=discord.Game(name="/help"))

# ==========================================
# COMANDOS (SLASH COMMANDS)
# ==========================================

@bot.tree.command(name="help", description="Muestra los comandos", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    mensaje = (
        "📦 **SISTEMA DE REQUERIMIENTOS**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "**/crear** [codigo] [estado] → Nuevo registro\n"
        "**/ver** [codigo] → Consulta historial y fechas\n"
        "**/actualizar** [codigo] [estado] → Cambia el estado\n"
        "**/lista** [filtro] → Ver todos los registros\n"
        "**/cerrar** [codigo] → Finaliza un registro"
    )
    await interaction.response.send_message(mensaje)

@bot.tree.command(name="crear", description="Crear un requerimiento", guild=GUILD)
async def crear(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo in data:
        return await interaction.response.send_message(f"❌ El código `{codigo}` ya existe.", ephemeral=True)

    ahora = get_lima_time()
    data[codigo] = {
        "estado": estado,
        "creado_el": ahora,
        "actualizado_el": ahora,
        "cerrado": False,
        "cerrado_el": None,
        "historial": [f"Creado: {estado} ({ahora})"]
    }
    save_data(data)
    await interaction.response.send_message(f"✅ Requerimiento **{codigo}** creado.")

@bot.tree.command(name="ver", description="Ver detalles", guild=GUILD)
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message(f"❌ No existe `{codigo}`.", ephemeral=True)

    info = data[codigo]
    historial = "\n".join([f"• {h}" for h in info["historial"]])
    estado_str = "🟢 ABIERTO" if not info["cerrado"] else f"🔴 CERRADO ({info['cerrado_el']})"

    msg = (
        f"📋 **REQUERIMIENTO: {codigo}**\n"
        f"**Estado:** {info['estado']} ({estado_str})\n"
        f"**Creación:** {info['creado_el']}\n"
        f"**Última Act.:** {info['actualizado_el']}\n"
        f"**Línea de Tiempo:**\n{historial}"
    )
    await interaction.response.send_message(msg)

@bot.tree.command(name="actualizar", description="Actualizar estado", guild=GUILD)
async def actualizar(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o ya está cerrado.", ephemeral=True)

    ahora = get_lima_time()
    data[codigo]["estado"] = estado
    data[codigo]["actualizado_el"] = ahora
    data[codigo]["historial"].append(f"Actualizado: {estado} ({ahora})")
    
    save_data(data)
    await interaction.response.send_message(f"🔄 **{codigo}** actualizado a `{estado}`.")

@bot.tree.command(name="lista", description="Listar registros", guild=GUILD)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Abiertos", value="abiertos"),
    app_commands.Choice(name="Cerrados", value="cerrados"),
    app_commands.Choice(name="Todos", value="todos")
])
async def lista(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    data = load_data()
    res = []
    for cod, info in data.items():
        cerrado = info.get("cerrado", False)
        linea = f"{'🔴' if cerrado else '🟢'} `{cod}` → {info['estado']}"
        if tipo.value == "abiertos" and not cerrado: res.append(linea)
        elif tipo.value == "cerrados" and cerrado: res.append(linea)
        elif tipo.value == "todos": res.append(linea)

    if not res: return await interaction.response.send_message("📭 Sin datos.")
    await interaction.response.send_message("\n".join(res[:20]))

# ==========================================
# CIERRE CON BOTONES
# ==========================================
class ConfirmarCerrar(discord.ui.View):
    def __init__(self, codigo):
        super().__init__(timeout=30)
        self.codigo = codigo

    @discord.ui.button(label="Cerrar permanentemente", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        if self.codigo in data:
            ahora = get_lima_time()
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            data[self.codigo]["historial"].append(f"CERRADO ({ahora})")
            save_data(data)
            await interaction.response.edit_message(content=f"🔒 **{self.codigo}** cerrado a las {ahora}.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Cancelado.", view=None)

@bot.tree.command(name="cerrar", description="Cerrar un registro", guild=GUILD)
async def cerrar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o ya está cerrado.", ephemeral=True)
    
    await interaction.response.send_message(f"⚠️ ¿Cerrar **{codigo}**?", view=ConfirmarCerrar(codigo))

# ==========================================
# INICIO DEL SERVICIO
# ==========================================
if __name__ == "__main__":
    keep_alive() # Inicia Flask
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")
