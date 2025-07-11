import os
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from flask import Flask
from threading import Thread
import unicodedata
import requests
import asyncio

app = Flask('')

@app.route('/')
def funzione():
    return "Bot attivo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# SETUP BOT
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# UTILITY
def normalizza(testo):
    testo = testo.lower().replace(" ", "").replace("-", "")
    return ''.join(
        c for c in unicodedata.normalize('NFD', testo)
        if unicodedata.category(c) != 'Mn'
    )

def trova_ruolo(nome, ruoli):
    nome_norm = normalizza(nome)
    for r in ruoli:
        if nome_norm == normalizza(r.name):
            return r
    for r in ruoli:
        n = normalizza(r.name)
        if nome_norm in n and not n.startswith("allievo"):
            return r
    return None

#----------------------------------------------------------------------------------------------------------------------------

#COMANDI GRUPPO
group_id = 8730810
allowed_role_id = 1226305676708679740

# Funzione di utilità per inizializzare client
def get_client():
    return Client(cookie="COOKIE")  # Sostituisci con il tuo cookie valido

# Gestione degli errori generali e rate limit
async def handle_action(ctx, action_func, action_name, username):
    try:
        await action_func()
        await ctx.send(f"L'utente **{username}** è stato {action_name} correttamente.", ephemeral=True)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", "5"))
            await ctx.send(
                f"⚠️ Roblox ha bloccato temporaneamente le richieste (rate limit). Riprova tra **{retry_after} secondi**.",
                ephemeral=True
            )
        else:
            await ctx.send(f"❌ Errore HTTP durante l'operazione: `{str(e)}`", ephemeral=True)
    except Exception as e:
        await ctx.send(f"❌ Errore generico durante l'operazione: `{str(e)}`", ephemeral=True)

# PROMOTE
@slash_command(name="promote_group", description="Promuove un utente nel gruppo Roblox")
@slash_option(name="username", description="Username dell'utente da promuovere", required=True, opt_type=OptionType.STRING)
async def promote_group(ctx: SlashContext, username: str):
    if allowed_role_id not in [role.id for role in ctx.author.roles]:
        return await ctx.send("⛔ Non hai il permesso per usare questo comando.", ephemeral=True)

    client = get_client()
    user = await client.get_user_by_username(username)
    group = await client.get_group(group_id)

    await handle_action(ctx, lambda: group.promote(user), "promosso", username)


# DEMOTE
@slash_command(name="demote_group", description="Degrada un utente nel gruppo Roblox")
@slash_option(name="username", description="Username dell'utente da degradare", required=True, opt_type=OptionType.STRING)
async def demote_group(ctx: SlashContext, username: str):
    if allowed_role_id not in [role.id for role in ctx.author.roles]:
        return await ctx.send("⛔ Non hai il permesso per usare questo comando.", ephemeral=True)

    client = get_client()
    user = await client.get_user_by_username(username)
    group = await client.get_group(group_id)

    await handle_action(ctx, lambda: group.demote(user), "degradato", username)


# ACCEPT
@slash_command(name="accept_group", description="Accetta un utente nel gruppo Roblox")
@slash_option(name="username", description="Username dell'utente da accettare", required=True, opt_type=OptionType.STRING)
async def accept_group(ctx: SlashContext, username: str):
    if allowed_role_id not in [role.id for role in ctx.author.roles]:
        return await ctx.send("⛔ Non hai il permesso per usare questo comando.", ephemeral=True)

    client = get_client()
    user = await client.get_user_by_username(username)
    group = await client.get_group(group_id)

    await handle_action(ctx, lambda: group.accept_user(user), "accettato", username)


# KICK
@slash_command(name="kick_group", description="Espelle un utente dal gruppo Roblox")
@slash_option(name="username", description="Username dell'utente da espellere", required=True, opt_type=OptionType.STRING)
async def kick_group(ctx: SlashContext, username: str):
    if allowed_role_id not in [role.id for role in ctx.author.roles]:
        return await ctx.send("⛔ Non hai il permesso per usare questo comando.", ephemeral=True)

    client = get_client()
    user = await client.get_user_by_username(username)
    group = await client.get_group(group_id)

    await handle_action(ctx, lambda: group.kick_user(user), "espulso", username)


# BAN
@slash_command(name="ban_group", description="Banna un utente dal gruppo Roblox")
@slash_option(name="username", description="Username dell'utente da bannare", required=True, opt_type=OptionType.STRING)
async def ban_group(ctx: SlashContext, username: str):
    if allowed_role_id not in [role.id for role in ctx.author.roles]:
        return await ctx.send("⛔ Non hai il permesso per usare questo comando.", ephemeral=True)

    client = get_client()
    user = await client.get_user_by_username(username)
    group = await client.get_group(group_id)

    await handle_action(ctx, lambda: group.exile_user_from_group(user), "bannato (esiliato)", username)

#---------------------------------------------------------------------------------------------------------------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        await bot.add_cog(GroupManagement(bot))
        synced = await bot.tree.sync()
        print(f"[DEBUG] Comandi sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[DEBUG] Errore sincronizzazione: {e}")
    print(f"[DEBUG] Bot pronto come {bot.user}")

#---------------------------------------------------------------------------------------------------------------------------

# AVVIO
if __name__ == "__main__":
    token = os.getenv("ACQUOLINA_TOKEN")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile ACQUOLINA_TOKEN non trovata.")
