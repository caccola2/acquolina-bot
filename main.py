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
class GroupManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roblosecurity = os.getenv("ROBLOX_COOKIE")
        self.group_id = 34146252  # ID fisso

    def get_user_id(self, username: str) -> int | None:
        try:
            r = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": True}
            )
            if r.status_code == 200:
                data = r.json()
                if data["data"]:
                    return data["data"][0]["id"]
            return None
        except Exception as e:
            print(f"[DEBUG] Errore nella richiesta get_user_id: {e}")
            return None

    def get_group_roles(self):
        r = requests.get(f"https://groups.roblox.com/v1/groups/{self.group_id}/roles")
        return r.json().get("roles", [])

    def get_csrf_token(self):
        """Ottiene il token CSRF per autenticare le richieste PATCH."""
        r = requests.post(
            "https://auth.roblox.com/v2/logout",
            headers={"Cookie": f".ROBLOSECURITY={self.roblosecurity}"}
        )
        return r.headers.get("x-csrf-token")

    def set_user_role(self, user_id: int, role_id: int) -> bool:
        csrf_token = self.get_csrf_token()
        headers = {
            "Cookie": f".ROBLOSECURITY={self.roblosecurity}",
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": csrf_token
        }
        r = requests.patch(
            f"https://groups.roblox.com/v1/groups/{self.group_id}/users/{user_id}",
            headers=headers,
            json={"roleId": role_id}
        )
        print(f"[DEBUG] PATCH status: {r.status_code} - {r.text}")
        return r.status_code == 200

    @app_commands.command(name="promote_group", description="Promuovi un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox", role_name="Nome del ruolo target")
    async def promote_group(self, interaction: Interaction, username: str, role_name: str):
        await interaction.response.defer()
        user_id = self.get_user_id(username)
        if not user_id:
            await interaction.followup.send("❌ Username non valido.")
            return

        roles = self.get_group_roles()
        target_role = next((r for r in roles if r["name"].lower() == role_name.lower()), None)
        if not target_role:
            await interaction.followup.send("❌ Ruolo non trovato.")
            return

        success = self.set_user_role(user_id, target_role["id"])
        await asyncio.sleep(1)
        if success:
            await interaction.followup.send(f"✅ {username} promosso a **{target_role['name']}**.")
        else:
            await interaction.followup.send("❌ Errore nella promozione. Verifica il cookie o i permessi.")

    @app_commands.command(name="demote_group", description="Degrada un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox", role_name="Ruolo attuale")
    async def demote_group(self, interaction: Interaction, username: str, role_name: str):
        await interaction.response.defer()
        user_id = self.get_user_id(username)
        if not user_id:
            await interaction.followup.send("❌ Username non valido.")
            return

        roles = sorted(self.get_group_roles(), key=lambda x: x["rank"])
        current_role = next((r for r in roles if r["name"].lower() == role_name.lower()), None)
        if not current_role:
            await interaction.followup.send("❌ Ruolo attuale non trovato.")
            return

        current_index = roles.index(current_role)
        if current_index == 0:
            await interaction.followup.send("❌ Nessun ruolo inferiore disponibile.")
            return

        new_role = roles[current_index - 1]
        success = self.set_user_role(user_id, new_role["id"])
        await asyncio.sleep(1)
        if success:
            await interaction.followup.send(f"🔻 {username} degradato a **{new_role['name']}**.")
        else:
            await interaction.followup.send("❌ Errore nella degradazione.")

    @app_commands.command(name="accept_group", description="Accetta un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox")
    async def accept_group(self, interaction: Interaction, username: str):
        await interaction.response.defer()
        user_id = self.get_user_id(username)
        if not user_id:
            await interaction.followup.send("❌ Username non valido.")
            return

        roles = sorted(self.get_group_roles(), key=lambda x: x["rank"])
        default_role = next((r for r in roles if r["rank"] > 0 and not r["name"].lower().startswith("guest")), None)
        if not default_role:
            await interaction.followup.send("❌ Nessun ruolo valido trovato.")
            return

        success = self.set_user_role(user_id, default_role["id"])
        if success:
            await interaction.followup.send(f"✅ {username} accettato nel gruppo con ruolo **{default_role['name']}**.")
        else:
            await interaction.followup.send("❌ Errore nell'assegnazione del ruolo. Verifica il cookie o i permessi.")

#---------------------------------------------------------------------------------------------------------------------------

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await bot.add_cog(GroupManagement(bot))
    try:
        synced = await bot.tree.sync()
        print(f"[DEBUG] Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"[DEBUG] Errore sincronizzazione: {e}")
    print(f"[DEBUG] Bot connesso come {bot.user}")

#---------------------------------------------------------------------------------------------------------------------------

# AVVIO
if __name__ == "__main__":
    token = os.getenv("ACQUOLINA_TOKEN")
    if token:
        print("[DEBUG] Avvio bot...")
        bot.run(token)
    else:
        print("[DEBUG] Variabile ACQUOLINA_TOKEN non trovata.")
