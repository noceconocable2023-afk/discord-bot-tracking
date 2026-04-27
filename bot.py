import discord
from discord.ext import commands
import json
import os

# 🔹 KEEP ALIVE (para Render Web Service)
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

# 👇 Inicia el mini servidor web
keep_alive()

# 🔹 CONFIGURACIÓN DISCORD
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

# Crear archivo si no existe
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

# Crear requerimiento
@bot.command()
async def crear(ctx, codigo, *, estado):
    data = load_data()
    data[codigo] = {
        "estado": estado,
        "historial": [estado]
    }
    save_data(data)
    await ctx.send(f"✅ {codigo} creado\nEstado: {estado}")

# Consultar estado
@bot.command()
async def estado(ctx, codigo):
    data = load_data()
    if codigo in data:
        await ctx.send(f"📦 {codigo}\nEstado: {data[codigo]['estado']}")
    else:
        await ctx.send("❌ No existe ese requerimiento")

# Actualizar estado
@bot.command()
async def actualizar(ctx, codigo, *, nuevo_estado):
    data = load_data()
    if codigo in data:
        data[codigo]["estado"] = nuevo_estado
        data[codigo]["historial"].append(nuevo_estado)
        save_data(data)
        await ctx.send(f"🔄 {codigo} actualizado\nEstado: {nuevo_estado}")
    else:
        await ctx.send("❌ No existe ese requerimiento")

# Ver historial
@bot.command()
async def historial(ctx, codigo):
    data = load_data()
    if codigo in data:
        historial = "\n- ".join(data[codigo]["historial"])
        await ctx.send(f"📜 Historial de {codigo}:\n- {historial}")
    else:
        await ctx.send("❌ No existe ese requerimiento")

# 🔐 TOKEN desde variables de entorno
bot.run(os.getenv("TOKEN"))
