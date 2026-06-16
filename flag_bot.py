import discord
from discord.ext import commands
import asyncio

# ─────────────────────────────────────────
#  CONFIGURAÇÃO — edita aqui
# ─────────────────────────────────────────
BOT_TOKEN = "o_teu_token_aqui"

# ID do canal onde o bot vai enviar a mensagem
CHANNEL_ID = 123456789

# (Opcional) ID de uma mensagem já existente — deixa None para o bot criar uma nova
MESSAGE_ID = None

# ─────────────────────────────────────────
#  MAPA: emoji da bandeira → nome do cargo
#  Podes adicionar/remover países à vontade
# ─────────────────────────────────────────
FLAG_TO_ROLE = {
    "🇵🇹": "🇵🇹 Português",
    "🇧🇷": "🇧🇷 Brasileiro",
    "🇬🇧": "🇬🇧 English",
    "🇺🇸": "🇺🇸 American",
    "🇷🇺": "🇷🇺 Russian",
    "🇪🇸": "🇪🇸 Español",
    "🇫🇷": "🇫🇷 Français",
    "🇩🇪": "🇩🇪 Deutsch",
    "🇮🇹": "🇮🇹 Italiano",
    "🇳🇱": "🇳🇱 Dutch",
    "🇵🇱": "🇵🇱 Polish",
    "🇹🇷": "🇹🇷 Turkish",
    "🇯🇵": "🇯🇵 Japanese",
    "🇰🇷": "🇰🇷 Korean",
    "🇨🇳": "🇨🇳 Chinese",
    "🇸🇦": "🇸🇦 Arabic",
}

# ─────────────────────────────────────────
#  MENSAGEM que o bot vai publicar no canal
# ─────────────────────────────────────────
EMBED_TITLE = "🌍 De onde és?"
EMBED_DESCRIPTION = (
    "Reage com a bandeira do teu país para receberes o cargo correspondente!\n\n"
    + "\n".join(f"{flag} → **{role}**" for flag, role in FLAG_TO_ROLE.items())
    + "\n\n*Só podes ter um cargo de país de cada vez.*"
)

# ─────────────────────────────────────────
#  BOT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Guarda o ID da mensagem de bandeiras em memória
flag_message_id: int | None = MESSAGE_ID


@bot.event
async def on_ready():
    global flag_message_id

    print(f"✅ Bot ligado como {bot.user} ({bot.user.id})")

    # Garante que os cargos existem no servidor
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"❌ Canal {CHANNEL_ID} não encontrado. Verifica o ID.")
        return

    guild = channel.guild
    await ensure_roles(guild)

    # Cria a mensagem de bandeiras se ainda não existir
    if flag_message_id is None:
        msg = await send_flag_message(channel)
        flag_message_id = msg.id
        print(f"📨 Mensagem de bandeiras criada (ID: {flag_message_id})")
    else:
        print(f"📨 A usar mensagem existente (ID: {flag_message_id})")


async def ensure_roles(guild: discord.Guild):
    """Cria os cargos que ainda não existam no servidor."""
    existing = {r.name for r in guild.roles}
    for role_name in FLAG_TO_ROLE.values():
        if role_name not in existing:
            await guild.create_role(
                name=role_name,
                mentionable=False,
                reason="Criado automaticamente pelo Flag Bot",
            )
            print(f"  ➕ Cargo criado: {role_name}")


async def send_flag_message(channel: discord.TextChannel) -> discord.Message:
    """Envia o embed com todas as bandeiras e adiciona as reações."""
    embed = discord.Embed(
        title=EMBED_TITLE,
        description=EMBED_DESCRIPTION,
        color=0x5865F2,  # cor Discord blurple
    )
    embed.set_footer(text="Flag Bot • Reage para escolher o teu país")

    msg = await channel.send(embed=embed)

    # Adiciona as reações ao embed automaticamente
    for flag in FLAG_TO_ROLE:
        await msg.add_reaction(flag)
        await asyncio.sleep(0.3)  # evita rate-limit

    return msg


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.Member):
    """Quando alguém reage → atribui cargo e remove os outros cargos de país."""
    if user.bot:
        return
    if reaction.message.id != flag_message_id:
        return

    emoji = str(reaction.emoji)
    role_name = FLAG_TO_ROLE.get(emoji)
    if role_name is None:
        return  # emoji que não está no mapa, ignora

    guild = reaction.message.guild
    new_role = discord.utils.get(guild.roles, name=role_name)
    if new_role is None:
        await ensure_roles(guild)
        new_role = discord.utils.get(guild.roles, name=role_name)

    # Remove todos os outros cargos de país que o utilizador tenha
    country_roles = [
        discord.utils.get(guild.roles, name=rn)
        for rn in FLAG_TO_ROLE.values()
        if rn != role_name
    ]
    roles_to_remove = [r for r in country_roles if r and r in user.roles]
    if roles_to_remove:
        await user.remove_roles(*roles_to_remove, reason="Flag Bot: mudança de país")

    # Atribui o novo cargo (se ainda não o tiver)
    if new_role not in user.roles:
        await user.add_roles(new_role, reason=f"Flag Bot: {emoji}")
        print(f"  ✅ {user.display_name} → {role_name}")


@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.Member):
    """Quando alguém remove a reação → remove o cargo correspondente."""
    if user.bot:
        return
    if reaction.message.id != flag_message_id:
        return

    emoji = str(reaction.emoji)
    role_name = FLAG_TO_ROLE.get(emoji)
    if role_name is None:
        return

    guild = reaction.message.guild
    role = discord.utils.get(guild.roles, name=role_name)
    if role and role in user.roles:
        await user.remove_roles(role, reason="Flag Bot: reação removida")
        print(f"  ➖ {user.display_name} → removido {role_name}")


# ─────────────────────────────────────────
#  COMANDO: !reenviar_bandeiras
#  (só para administradores)
# ─────────────────────────────────────────
@bot.command(name="reenviar_bandeiras")
@commands.has_permissions(administrator=True)
async def resend_flags(ctx: commands.Context):
    """Apaga a mensagem antiga e envia uma nova."""
    global flag_message_id

    channel = bot.get_channel(CHANNEL_ID)
    if flag_message_id:
        try:
            old_msg = await channel.fetch_message(flag_message_id)
            await old_msg.delete()
        except discord.NotFound:
            pass

    msg = await send_flag_message(channel)
    flag_message_id = msg.id
    await ctx.send(f"✅ Mensagem de bandeiras reenviada! (ID: {flag_message_id})", delete_after=10)


bot.run(BOT_TOKEN)
