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
REQUIRED_ROLE_ID = 1226305676708679740

class GroupManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roblosecurity = os.getenv("ROBLOX_COOKIE")
        self.headers = {
            "Cookie": f".ROBLOSECURITY={self.roblosecurity}",
            "Content-Type": "application/json"
        }
        self.group_id = 34146252

    def has_required_role(self, interaction: Interaction) -> bool:
        member = interaction.guild.get_member(interaction.user.id)
        return member is not None and any(role.id == REQUIRED_ROLE_ID for role in member.roles)

    def get_user_id(self, username: str) -> int | None:
        try:
            r = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": False}
            )
            if r.status_code == 200:
                data = r.json()
                if data["data"]:
                    return data["data"][0]["id"]
            return None
        except Exception as e:
            print(f"[DEBUG] get_user_id error: {e}")
            return None

    def get_user_group_info(self, user_id: int):
        try:
            r = requests.get(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles")
            if r.status_code == 200:
                data = r.json()
                for group in data["data"]:
                    if group["group"]["id"] == self.group_id:
                        return group["role"]
        except Exception as e:
            print(f"[DEBUG] get_user_group_info error: {e}")
        return None

    def get_group_roles(self):
        r = requests.get(f"https://groups.roblox.com/v1/groups/{self.group_id}/roles")
        return r.json().get("roles", [])

    def set_user_role(self, user_id: int, role_id: int) -> bool:
        r = requests.patch(
            f"https://groups.roblox.com/v1/groups/{self.group_id}/users/{user_id}",
            headers=self.headers,
            json={"roleId": role_id}
        )
        print(f"[DEBUG] set_user_role: {r.status_code} - {r.text}")
        return r.status_code == 200

    def exile_user_from_group(self, user_id: int) -> bool:
        try:
            r = requests.delete(
                f"https://groups.roblox.com/v1/groups/{self.group_id}/users/{user_id}",
                headers=self.headers
            )
            print(f"[DEBUG] exile_user_from_group: {r.status_code} - {r.text}")
            return r.status_code == 200
        except Exception as e:
            print(f"[DEBUG] exile_user_from_group error: {e}")
            return False

    @app_commands.command(name="promote_group", description="Promuovi un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox", role_name="Nome del ruolo target")
    async def promote_group(self, interaction: Interaction, username: str, role_name: str):
        if not self.has_required_role(interaction):
            return await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        user_id = self.get_user_id(username)
        if not user_id:
            return await interaction.followup.send("❌ Username non valido.", ephemeral=True)

        current_role = self.get_user_group_info(user_id)
        if current_role and current_role["name"].lower() == role_name.lower():
            return await interaction.followup.send("ℹ️ L'utente ha già questo ruolo.", ephemeral=True)

        roles = self.get_group_roles()
        target_role = next((r for r in roles if r["name"].lower() == role_name.lower()), None)
        if not target_role:
            return await interaction.followup.send("❌ Ruolo non trovato.", ephemeral=True)

        if self.set_user_role(user_id, target_role["id"]):
            return await interaction.followup.send(f"✅ {username} promosso a **{target_role['name']}**.", ephemeral=True)
        await interaction.followup.send("❌ Errore nella promozione.", ephemeral=True)

    @app_commands.command(name="demote_group", description="Degrada un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox", role_name="Ruolo attuale")
    async def demote_group(self, interaction: Interaction, username: str, role_name: str):
        if not self.has_required_role(interaction):
            return await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        user_id = self.get_user_id(username)
        if not user_id:
            return await interaction.followup.send("❌ Username non valido.", ephemeral=True)

        roles = sorted(self.get_group_roles(), key=lambda x: x["rank"])
        current_role = next((r for r in roles if r["name"].lower() == role_name.lower()), None)
        if not current_role:
            return await interaction.followup.send("❌ Ruolo attuale non trovato.", ephemeral=True)

        index = roles.index(current_role)
        if index == 0:
            return await interaction.followup.send("❌ Nessun ruolo inferiore disponibile.", ephemeral=True)

        new_role = roles[index - 1]
        if self.set_user_role(user_id, new_role["id"]):
            return await interaction.followup.send(f"🔻 {username} degradato a **{new_role['name']}**.", ephemeral=True)
        await interaction.followup.send("❌ Errore nella degradazione.", ephemeral=True)

    @app_commands.command(name="accept_group", description="Accetta un utente nel gruppo Roblox.")
    @app_commands.describe(username="Username Roblox", role_name="Ruolo da assegnare")
    async def accept_group(self, interaction: Interaction, username: str, role_name: str):
        if not self.has_required_role(interaction):
            return await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        user_id = self.get_user_id(username)
        if not user_id:
            return await interaction.followup.send("❌ Username non valido.", ephemeral=True)

        if self.get_user_group_info(user_id):
            return await interaction.followup.send("ℹ️ L'utente è già nel gruppo.", ephemeral=True)

        roles = self.get_group_roles()
        role = next((r for r in roles if r["name"].lower() == role_name.lower()), None)
        if not role or role["rank"] <= 0:
            return await interaction.followup.send("❌ Ruolo non valido o troppo basso.", ephemeral=True)

        if self.set_user_role(user_id, role["id"]):
            return await interaction.followup.send(f"✅ {username} accettato con ruolo **{role['name']}**.", ephemeral=True)
        await interaction.followup.send("❌ Errore durante l'assegnazione del ruolo.", ephemeral=True)

    @app_commands.command(name="kick_group", description="Espelli un utente dal gruppo Roblox.")
    @app_commands.describe(username="Username da espellere")
    async def kick_group(self, interaction: Interaction, username: str):
        if not self.has_required_role(interaction):
            return await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        user_id = self.get_user_id(username)
        if not user_id:
            return await interaction.followup.send("❌ Username non valido.", ephemeral=True)

        if self.exile_user_from_group(user_id):
            return await interaction.followup.send(f"👢 {username} espulso dal gruppo.", ephemeral=True)
        await interaction.followup.send("❌ Errore durante l'espulsione.", ephemeral=True)

    @app_commands.command(name="ban_group", description="Banna un utente dal gruppo Roblox.")
    @app_commands.describe(username="Username da bannare")
    async def ban_group(self, interaction: Interaction, username: str):
        if not self.has_required_role(interaction):
            return await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        user_id = self.get_user_id(username)
        if not user_id:
            return await interaction.followup.send("❌ Username non valido.", ephemeral=True)

        if self.exile_user_from_group(user_id):
            return await interaction.followup.send(f"⛔ {username} è stato **bannato** dal gruppo.", ephemeral=True)
        await interaction.followup.send("❌ Errore durante il ban.", ephemeral=True)

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
