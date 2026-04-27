import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# ==========================================
# CONFIGURACIÓN DE FLASK (Keep Alive)
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

# Flujo de estados numerados
ESTADOS_PROGRESO = [
    "1. PENDIENTE DE ACEPTACIÓN",
    "2. PENDIENTE DE APROBACIÓN",
    "3. PENDIENTE DE COMPRA",
    "4. PENDIENTE DE ENVÍO",
    "5. PENDIENTE DE RECOJO",
    "6. ENTREGADO"
]

# ==========================================
# GESTIÓN DE DATOS
# ==========================================
def load_data():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r") as f: return json.load(f)
    except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

# ==========================================
# VISTAS (Botones de Confirmación)
# ==========================================
class ConfirmarAccion(discord.ui.View):
    def __init__(self, codigo, accion, nuevo_estado=None):
        super().__init__(timeout=30)
        self.codigo = codigo
        self.accion = accion 
        self.nuevo_estado = nuevo_estado

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        if self.codigo not in data:
            return await interaction.response.edit_message(content="❌ El código ya no existe.", view=None)

        ahora = get_lima_time()

        if self.accion == "actualizar_final":
            data[self.codigo]["estado"] = self.nuevo_estado
            data[self.codigo]["actualizado_el"] = ahora
            data[self.codigo]["historial"].append(f"Actualizado: {self.nuevo_estado} ({ahora})")
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            await interaction.response.edit_message(content=f"✅ **{self.codigo}** actualizado a `{self.nuevo_estado}` y finalizado.", view=None)
        
        elif self.accion == "eliminar":
            del data[self.codigo]
            await interaction.response.edit_message(content=f"🗑️ Registro **{self.codigo}** eliminado permanentemente.", view=None)

        elif self.accion == "retroceder":
            req = data[self.codigo]
            if len(req["historial"]) > 1:
                req["historial"].pop()
                ultimo_log = req["historial"][-1]
                nuevo_estado = ultimo_log.split(":")[1].split("(")[0].strip()
                req["estado"] = nuevo_estado
                req["actualizado_el"] = ahora
                req["cerrado"] = False
                req["cerrado_el"] = None
                await interaction.response.edit_message(content=f"⏮️ **{self.codigo}** regresó a: `{nuevo_estado}`.", view=None)
            else:
                return await interaction.response.edit_message(content="⚠️ No hay historial para retroceder.", view=None)

        save_data(data)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Operación cancelada.", view=None)

# ==========================================
# EVENTOS
# ==========================================
@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD)
    print(f"✅ Bot operativo: {bot.user}")

# ==========================================
# COMANDOS
# ==========================================

@bot.tree.command(name="help", description="Guía de comandos del sistema", guild=GUILD)
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📦 Guía del Sistema de Requerimientos", color=discord.Color.blue())
    embed.add_field(name="🆕 /crear", value="Inicia un registro con el estado '1. PENDIENTE DE ACEPTACIÓN'.", inline=False)
    embed.add_field(name="🔄 /actualizar", value="Permite avanzar a cualquier estado posterior o Cancelar.", inline=False)
    embed.add_field(name="⏮️ /retroceder", value="Elimina el último cambio y vuelve al estado anterior.", inline=False)
    embed.add_field(name="🔍 /ver", value="Muestra el estado actual y toda la línea de tiempo.", inline=False)
    embed.add_field(name="📋 /lista", value="Filtra registros por Abiertos, Entregados, Cancelados o Todos.", inline=False)
    embed.add_field(name="🗑️ /eliminar", value="Borra permanentemente un código del sistema.", inline=False)
    embed.add_field(name="💾 /respaldo", value="Envía el archivo data.json para guardar copia de seguridad.", inline=False)
    embed.set_footer(text="Nota: Entregados y Cancelados cierran el registro automáticamente.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="respaldo", description="Obtener copia de seguridad", guild=GUILD)
async def respaldo(interaction: discord.Interaction):
    if not os.path.exists(DATA_FILE): return await interaction.response.send_message("❌ No hay datos.", ephemeral=True)
    await interaction.response.send_message("📂 Archivo de respaldo:", file=discord.File(DATA_FILE))

@bot.tree.command(name="crear", description="Crear registro nuevo", guild=GUILD)
async def crear(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo in data: return await interaction.response.send_message(f"❌ `{codigo}` ya existe.", ephemeral=True)
    
    ahora = get_lima_time()
    estado = ESTADOS_PROGRESO[0]
    data[codigo] = {"estado": estado, "creado_el": ahora, "actualizado_el": ahora, "cerrado": False, "cerrado_el": None, "historial": [f"Creado: {estado} ({ahora})"]}
    save_data(data)
    await interaction.response.send_message(f"✅ **{codigo}** creado en `{estado}`.")

@bot.tree.command(name="actualizar", description="Cambiar a un estado posterior", guild=GUILD)
async def actualizar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o ya está cerrado.", ephemeral=True)

    estado_actual = data[codigo]["estado"]
    idx_actual = ESTADOS_PROGRESO.index(estado_actual)
    
    # Opciones: Todos los estados que siguen en la lista + CANCELADO
    opciones = []
    for i in range(idx_actual + 1, len(ESTADOS_PROGRESO)):
        opciones.append(app_commands.Choice(name=ESTADOS_PROGRESO[i], value=ESTADOS_PROGRESO[i]))
    opciones.append(app_commands.Choice(name="❌ CANCELADO", value="CANCELADO"))

    # Vista con menú desplegable para elegir el nuevo estado
    class SelectView(discord.ui.View):
        def __init__(self, opts):
            super().__init__(timeout=30)
            self.add_item(self.create_select(opts))

        def create_select(self, opts):
            select = discord.ui.Select(placeholder="Selecciona el nuevo estado...")
            for opt in opts:
                select.add_option(label=opt.name, value=opt.value)
            
            async def callback(it: discord.Interaction):
                val = select.values[0]
                if val == "CANCELADO" or val == "6. ENTREGADO":
                    await it.response.send_message(f"⚠️ ¿Confirmas pasar **{codigo}** a `{val}`? Esto cerrará el registro.", view=ConfirmarAccion(codigo, "actualizar_final", val))
                else:
                    data[codigo]["estado"] = val
                    data[codigo]["actualizado_el"] = get_lima_time()
                    data[codigo]["historial"].append(f"Actualizado: {val} ({data[codigo]['actualizado_el']})")
                    save_data(data)
                    await it.response.send_message(f"🔄 **{codigo}** actualizado a `{val}`.")
            
            select.callback = callback
            return select

    await interaction.response.send_message(f"Elige el siguiente paso para **{codigo}**:", view=SelectView(opciones), ephemeral=True)

@bot.tree.command(name="ver", description="Ver detalles", guild=GUILD)
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data: return await interaction.response.send_message("❌ No encontrado.", ephemeral=True)
    info = data[codigo]
    historial = "\n".join([f"• {h}" for h in info["historial"]])
    await interaction.response.send_message(f"📋 **DETALLES: {codigo}**\n**Estado:** `{info['estado']}`\n**Status:** {'🟢 ABIERTO' if not info['cerrado'] else '🔴 CERRADO'}\n\n**Historial:**\n{historial}")

@bot.tree.command(name="retroceder", description="Deshacer cambio", guild=GUILD)
async def retroceder(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or len(data[codigo]["historial"]) <= 1:
        return await interaction.response.send_message("❌ No se puede retroceder.", ephemeral=True)
    await interaction.response.send_message(f"⏮️ ¿Deshacer último cambio de **{codigo}**?", view=ConfirmarAccion(codigo, "retroceder"))

@bot.tree.command(name="lista", description="Ver registros filtrados", guild=GUILD)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Abiertos", value="abiertos"),
    app_commands.Choice(name="Entregados", value="entregados"),
    app_commands.Choice(name="Cancelados", value="cancelados"),
    app_commands.Choice(name="Todos", value="todos")
])
async def lista(interaction: discord.Interaction, tipo: app_commands.Choice[str]):
    data = load_data()
    res = []
    for cod, info in data.items():
        est = info["estado"]
        cerrado = info.get("cerrado")
        
        linea = f"{'🟢' if not cerrado else '🔴'} `{cod}` → {est}"
        
        if tipo.value == "todos": res.append(linea)
        elif tipo.value == "abiertos" and not cerrado: res.append(linea)
        elif tipo.value == "entregados" and est == "6. ENTREGADO": res.append(linea)
        elif tipo.value == "cancelados" and est == "CANCELADO": res.append(linea)

    await interaction.response.send_message(f"📋 **Lista: {tipo.name}**\n" + ("\n".join(res[:20]) if res else "No hay registros."))

@bot.tree.command(name="eliminar", description="Eliminar registro", guild=GUILD)
async def eliminar(interaction: discord.Interaction, codigo: str):
    if codigo not in load_data(): return await interaction.response.send_message("❌ No existe.", ephemeral=True)
    await interaction.response.send_message(f"🚨 ¿Eliminar `{codigo}`?", view=ConfirmarAccion(codigo, "eliminar"))

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
