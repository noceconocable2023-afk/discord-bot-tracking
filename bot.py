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
# VISTAS DE INTERACCIÓN (Botones de Confirmación)
# ==========================================
class ConfirmarAccion(discord.ui.View):
    def __init__(self, codigo, accion):
        super().__init__(timeout=20)
        self.codigo = codigo
        self.accion = accion # "cerrar", "eliminar" o "retroceder"

    @discord.ui.button(label="Confirmar Acción", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        if self.codigo not in data:
            return await interaction.response.edit_message(content="❌ Error: El código ya no existe.", view=None)

        ahora = get_lima_time()

        if self.accion == "cerrar":
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            data[self.codigo]["historial"].append(f"CERRADO ({ahora})")
            await interaction.response.edit_message(content=f"🔒 Requerimiento **{self.codigo}** finalizado y cerrado.", view=None)
        
        elif self.accion == "eliminar":
            del data[self.codigo]
            await interaction.response.edit_message(content=f"🗑️ Registro **{self.codigo}** eliminado permanentemente del sistema.", view=None)

        elif self.accion == "retroceder":
            req = data[self.codigo]
            if len(req["historial"]) > 1:
                req["historial"].pop() # Borramos el último cambio
                ultimo_log = req["historial"][-1]
                # Extraemos el estado anterior del texto del historial
                nuevo_estado = ultimo_log.split(":")[1].split("(")[0].strip()
                req["estado"] = nuevo_estado
                req["actualizado_el"] = ahora
                req["cerrado"] = False
                req["cerrado_el"] = None
                await interaction.response.edit_message(content=f"⏮️ Se deshizo el último cambio. **{self.codigo}** volvió al estado: `{nuevo_estado}`.", view=None)
            else:
                return await interaction.response.edit_message(content="⚠️ No hay más historial para retroceder.", view=None)

        save_data(data)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Acción cancelada por el usuario.", view=None)

# ==========================================
# EVENTOS
# ==========================================
@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD)
    print(f"✅ Bot operativo: {bot.user}")

# ==========================================
# COMANDOS (SLASH COMMANDS)
# ==========================================

@bot.tree.command(name="help", description="Guía detallada de comandos", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📦 Sistema de Gestión de Requerimientos",
        description="Gestiona tus registros de manera eficiente con los siguientes comandos:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🆕 /crear", value="Registra un nuevo código y su estado inicial.", inline=False)
    embed.add_field(name="🔍 /ver", value="Muestra el estado, fechas e historial completo.", inline=False)
    embed.add_field(name="🔄 /actualizar", value="Cambia el estado actual del requerimiento.", inline=False)
    embed.add_field(name="⏮️ /retroceder", value="Elimina la última actualización (Pide confirmación).", inline=False)
    embed.add_field(name="📋 /lista", value="Ver todos los registros abiertos o cerrados.", inline=False)
    embed.add_field(name="🔒 /cerrar", value="Finaliza un requerimiento permanentemente.", inline=False)
    embed.add_field(name="🗑️ /eliminar", value="Borra todo rastro del código en el sistema.", inline=False)
    embed.set_footer(text="Zona Horaria configurada: Lima, Perú (UTC-5)")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="crear", description="Registrar nuevo requerimiento", guild=GUILD)
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
    await interaction.response.send_message(f"✅ Requerimiento **{codigo}** registrado exitosamente.")

@bot.tree.command(name="ver", description="Ver historial y estado", guild=GUILD)
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message(f"❌ No se encontró el código `{codigo}`.", ephemeral=True)

    info = data[codigo]
    historial = "\n".join([f"• {h}" for h in info["historial"]])
    estado_status = "🟢 ABIERTO" if not info["cerrado"] else f"🔴 CERRADO ({info['cerrado_el']})"

    msg = (
        f"📋 **DETALLES: {codigo}**\n"
        f"**Estado Actual:** `{info['estado']}`\n"
        f"**Disponibilidad:** {estado_status}\n"
        f"**Creación:** {info['creado_el']}\n\n"
        f"**Línea de Tiempo:**\n{historial}"
    )
    await interaction.response.send_message(msg)

@bot.tree.command(name="actualizar", description="Cambiar estado del requerimiento", guild=GUILD)
async def actualizar(interaction: discord.Interaction, codigo: str, estado: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ El registro no existe o ya está cerrado.", ephemeral=True)

    ahora = get_lima_time()
    data[codigo]["estado"] = estado
    data[codigo]["actualizado_el"] = ahora
    data[codigo]["historial"].append(f"Actualizado: {estado} ({ahora})")
    
    save_data(data)
    await interaction.response.send_message(f"🔄 **{codigo}** actualizado al estado: `{estado}`.")

@bot.tree.command(name="retroceder", description="Deshacer último cambio", guild=GUILD)
async def retroceder(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message("❌ El código no existe.", ephemeral=True)
    
    if len(data[codigo]["historial"]) <= 1:
        return await interaction.response.send_message("⚠️ No hay cambios que deshacer en este registro.", ephemeral=True)

    await interaction.response.send_message(
        f"⏮️ ¿Estás seguro que deseas eliminar la última actualización de **{codigo}**?", 
        view=ConfirmarAccion(codigo, "retroceder")
    )

@bot.tree.command(name="lista", description="Listar registros guardados", guild=GUILD)
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

    if not res: return await interaction.response.send_message("📭 No hay registros para mostrar.")
    await interaction.response.send_message(f"📋 **Lista de Requerimientos ({tipo.name}):**\n" + "\n".join(res[:20]))

@bot.tree.command(name="cerrar", description="Cerrar requerimiento", guild=GUILD)
async def cerrar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ El registro no existe o ya está cerrado.", ephemeral=True)
    await interaction.response.send_message(f"⚠️ ¿Confirmas el cierre definitivo de **{codigo}**?", view=ConfirmarAccion(codigo, "cerrar"))

@bot.tree.command(name="eliminar", description="Borrar registro permanentemente", guild=GUILD)
async def eliminar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data:
        return await interaction.response.send_message("❌ El código no existe.", ephemeral=True)
    await interaction.response.send_message(f"🚨 **ALERTA**: ¿Deseas eliminar permanentemente `{codigo}`?", view=ConfirmarAccion(codigo, "eliminar"))

# ==========================================
# INICIO DEL SERVICIO
# ==========================================
if __name__ == "__main__":
    keep_alive()
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error crítico al iniciar el bot: {e}")
