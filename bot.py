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
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# CONFIGURACIÓN DEL BOT Y ZONA HORARIA
# ==========================================
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1493618366093459669 
GUILD = discord.Object(id=GUILD_ID)

def get_lima_time():
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
    await bot.tree.sync(guild=GUILD)
    print(f"✅ Bot operativo: {bot.user}")

# ==========================================
# COMANDOS (SLASH COMMANDS)
# ==========================================

@bot.tree.command(name="help", description="Muestra los comandos", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    mensaje = (
        "📦 **SISTEMA DE REQUERIMIENTOS**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "**/crear** `[codigo]` `[estado]` → Nuevo registro\n"
        "**/ver** `[codigo]` → Ver historial y fechas\n"
        "**/actualizar** `[codigo]` `[estado]` → Nuevo estado\n"
        "**/retroceder** `[codigo]` → Borra última actualización\n"
        "**/lista** `[filtro]` → Ver registros (Abiertos/Cerrados)\n"
        "**/cerrar** `[codigo]` → Finaliza registro\n"
        "**/eliminar** `[codigo]` → Borra todo el registro"
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
        f"**Última Act.:** {info['actualizado_el']}\n\n"
        f"**Línea de Tiempo:**\n{historial}"
    )
    await interaction.response.send_message(msg)

@bot.tree.command(name="actualizar", description="Actualizar estado", guild=GUILD)
async def actualizar(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o está cerrado.", ephemeral=True)

    ahora = get_lima_time()
    data[codigo]["estado"] = estado
    data[codigo]["actualizado_el"] = ahora
    data[codigo]["historial"].append(f"Actualizado: {estado} ({ahora})")
    
    save_data(data)
    await interaction.response.send_message(f"🔄 **{codigo}** actualizado a `{estado}`.")

@bot.tree.command(name="retroceder", description="Eliminar la última actualización de estado", guild=GUILD)
async def retroceder(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message("❌ No existe ese código.", ephemeral=True)
    
    req = data[codigo]
    if len(req["historial"]) <= 1:
        return await interaction.response.send_message("⚠️ No hay estados previos para retroceder.", ephemeral=True)

    # Eliminar el último del historial
    req["historial"].pop()
    
    # El nuevo estado actual es el que quedó al final de la lista
    ultimo_log = req["historial"][-1]
    # Extraemos el nombre del estado (asumiendo formato "Estado: Nombre (Fecha)")
    nuevo_estado = ultimo_log.split(":")[1].split("(")[0].strip()
    
    req["estado"] = nuevo_estado
    req["actualizado_el"] = get_lima_time()
    req["cerrado"] = False # Si estaba cerrado, lo reabre al retroceder
    req["cerrado_el"] = None

    save_data(data)
    await interaction.response.send_message(f"⏮️ Se ha retrocedido el requerimiento **{codigo}** al estado: `{nuevo_estado}`.")

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
    await interaction.response.send_message(f"📋 **Lista ({tipo.name}):**\n" + "\n".join(res[:20]))

# ==========================================
# CIERRES Y ELIMINACIÓN CON BOTONES
# ==========================================
class ConfirmarAccion(discord.ui.View):
    def __init__(self, codigo, accion):
        super().__init__(timeout=20)
        self.codigo = codigo
        self.accion = accion # "cerrar" o "eliminar"

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        if self.codigo not in data:
            return await interaction.response.edit_message(content="❌ El código ya no existe.", view=None)

        if self.accion == "cerrar":
            ahora = get_lima_time()
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            data[self.codigo]["historial"].append(f"CERRADO ({ahora})")
            save_data(data)
            await interaction.response.edit_message(content=f"🔒 **{self.codigo}** cerrado el {ahora}.", view=None)
        
        elif self.accion == "eliminar":
            del data[self.codigo]
            save_data(data)
            await interaction.response.edit_message(content=f"🗑️ Registro **{self.codigo}** eliminado permanentemente.", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Acción cancelada.", view=None)

@bot.tree.command(name="cerrar", description="Cerrar un registro", guild=GUILD)
async def cerrar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o ya está cerrado.", ephemeral=True)
    await interaction.response.send_message(f"⚠️ ¿Cerrar **{codigo}**?", view=ConfirmarAccion(codigo, "cerrar"))

@bot.tree.command(name="eliminar", description="Eliminar registro permanentemente", guild=GUILD)
async def eliminar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message("❌ El código no existe.", ephemeral=True)
    await interaction.response.send_message(f"🚨 **¡ATENCIÓN!** ¿Eliminar por completo `{codigo}`? Esta acción no se puede deshacer.", view=ConfirmarAccion(codigo, "eliminar"))

# ==========================================
# INICIO DEL SERVICIO
# ==========================================
if __name__ == "__main__":
    keep_alive()
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error: {e}")
