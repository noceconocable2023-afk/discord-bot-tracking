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
def home(): return "Servidor operativo"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# CONFIGURACIÓN DEL BOT
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

ORDEN_ESTADOS = [
    "PENDIENTE DE ACEPTACIÓN", "PENDIENTE DE APROBACIÓN", "PENDIENTE DE COMPRA",
    "PENDIENTE DE ENVÍO", "PENDIENTE DE RECOJO", "ENTREGADO"
]

def load_data():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r") as f: return json.load(f)
    except: return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

# ==========================================
# VISTAS DE INTERACCIÓN
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
            data[self.codigo]["cerrado"] = True
            data[self.codigo]["cerrado_el"] = ahora
            data[self.codigo]["historial"].append(f"Actualizado: {self.nuevo_estado} ({ahora})")
            await interaction.response.edit_message(content=f"✅ **{self.codigo}** finalizado.", view=None)
        
        elif self.accion == "eliminar":
            del data[self.codigo]
            await interaction.response.edit_message(content=f"🗑️ Registro **{self.codigo}** eliminado.", view=None)

        elif self.accion == "retroceder":
            req = data[self.codigo]
            if len(req["historial"]) > 1:
                req["historial"].pop()
                ultimo_log = req["historial"][-1]
                nuevo_estado = ultimo_log.split(":")[1].split("(")[0].strip()
                req["estado"] = nuevo_estado
                req["cerrado"] = False
                await interaction.response.edit_message(content=f"⏮️ **{self.codigo}** regresó a `{nuevo_estado}`.", view=None)
        
        save_data(data)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Acción cancelada.", view=None)

# ==========================================
# COMANDOS
# ==========================================

@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD)
    print(f"✅ Bot listo: {bot.user}")

@bot.tree.command(name="crear", description="Iniciar un nuevo requerimiento con asunto", guild=GUILD)
@app_commands.describe(codigo="Código único (ej: REQ001)", asunto="Descripción corta (ej: Laptops Oficina)")
async def crear(interaction: discord.Interaction, codigo: str, asunto: str):
    data = load_data()
    if codigo in data: return await interaction.response.send_message(f"❌ `{codigo}` ya existe.", ephemeral=True)
    
    ahora = get_lima_time()
    estado = ORDEN_ESTADOS[0]
    data[codigo] = {
        "asunto": asunto.upper(),
        "estado": estado, 
        "creado_el": ahora, 
        "cerrado": False, 
        "historial": [f"Creado: {estado} ({ahora})"]
    }
    save_data(data)
    await interaction.response.send_message(f"✅ **{codigo}** ({asunto.upper()}) creado en `{estado}`.")

@bot.tree.command(name="actualizar", description="Avanzar estado", guild=GUILD)
async def actualizar(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data or data[codigo].get("cerrado"):
        return await interaction.response.send_message("❌ No existe o está cerrado.", ephemeral=True)

    idx_actual = ORDEN_ESTADOS.index(data[codigo]["estado"])
    opciones = [app_commands.Choice(name=ORDEN_ESTADOS[i], value=ORDEN_ESTADOS[i]) for i in range(idx_actual + 1, len(ORDEN_ESTADOS))]
    opciones.append(app_commands.Choice(name="CANCELADO", value="CANCELADO"))

    class SelectView(discord.ui.View):
        def __init__(self, opts):
            super().__init__(timeout=30)
            select = discord.ui.Select(placeholder=f"Asunto: {data[codigo]['asunto']}...")
            for opt in opts: select.add_option(label=opt.name, value=opt.value)
            async def callback(it: discord.Interaction):
                val = select.values[0]
                if val in ["CANCELADO", "ENTREGADO"]:
                    await it.response.send_message(f"⚠️ ¿Cerrar **{codigo}**?", view=ConfirmarAccion(codigo, "actualizar_final", val))
                else:
                    data[codigo].update({"estado": val, "actualizado_el": get_lima_time()})
                    data[codigo]["historial"].append(f"Actualizado: {val} ({get_lima_time()})")
                    save_data(data)
                    await it.response.send_message(f"🔄 **{codigo}** → `{val}`")
            select.callback = callback
            self.add_item(select)

    await interaction.response.send_message(f"Actualizar **{codigo}**:", view=SelectView(opciones), ephemeral=True)

@bot.tree.command(name="ver", description="Detalles completos", guild=GUILD)
async def ver(interaction: discord.Interaction, codigo: str):
    data = load_data()
    if codigo not in data: return await interaction.response.send_message("❌ No encontrado.", ephemeral=True)
    info = data[codigo]
    
    color = 0x9B59B6 if info["estado"] == "ENTREGADO" else (discord.Color.red() if info["estado"] == "CANCELADO" else discord.Color.green())
    embed = discord.Embed(title=f"📋 {codigo}: {info.get('asunto', 'SIN ASUNTO')}", color=color)
    embed.add_field(name="Estado Actual", value=f"`{info['estado']}`", inline=True)
    embed.add_field(name="Status", value="🟢 ABIERTO" if not info['cerrado'] else "🔴 FINALIZADO", inline=True)
    embed.add_field(name="Línea de Tiempo", value="\n".join([f"• {h}" for h in info["historial"]]), inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lista", description="Listar registros", guild=GUILD)
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
        est, cerrado, asunto = info["estado"], info.get("cerrado"), info.get("asunto", "S/A")
        icono = "🟣" if est == "ENTREGADO" else ("🔴" if est == "CANCELADO" else "🟢")
        linea = f"{icono} `{cod}` | **{asunto}** → {est}"
        
        if tipo.value == "todos" or \
           (tipo.value == "abiertos" and not cerrado) or \
           (tipo.value == "entregados" and est == "ENTREGADO") or \
           (tipo.value == "cancelados" and est == "CANCELADO"):
            res.append(linea)

    await interaction.response.send_message(f"📋 **Lista: {tipo.name}**\n" + ("\n".join(res[:25]) if res else "Vacío."))

@bot.tree.command(name="respaldo", description="Descargar backup", guild=GUILD)
async def respaldo(interaction: discord.Interaction):
    if os.path.exists(DATA_FILE): await interaction.response.send_message("📂 Backup:", file=discord.File(DATA_FILE))

@bot.tree.command(name="restaurar", description="Subir backup", guild=GUILD)
async def restaurar(interaction: discord.Interaction, archivo: discord.Attachment):
    if archivo.filename.endswith(".json"):
        save_data(json.loads(await archivo.read()))
        await interaction.response.send_message("✅ Datos restaurados.")

@bot.tree.command(name="retroceder", description="Deshacer cambio", guild=GUILD)
async def retroceder(interaction: discord.Interaction, codigo: str):
    if codigo in load_data(): await interaction.response.send_message(f"⏮️ ¿Deshacer último paso de **{codigo}**?", view=ConfirmarAccion(codigo, "retroceder"))

@bot.tree.command(name="eliminar", description="Borrar registro", guild=GUILD)
async def eliminar(interaction: discord.Interaction, codigo: str):
    if codigo in load_data(): await interaction.response.send_message(f"🚨 ¿Eliminar `{codigo}`?", view=ConfirmarAccion(codigo, "eliminar"))

@bot.tree.command(name="help", description="Ayuda", guild=GUILD)
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("📖 Comandos: `/crear` (con asunto), `/actualizar`, `/ver`, `/lista`, `/retroceder`, `/eliminar`, `/respaldo`, `/restaurar`.")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
