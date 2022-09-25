from __future__ import annotations
import traceback
from typing import TYPE_CHECKING, Union
import disnake
from disnake.ext import commands
from .errors import NoVoice, NoPlayer, NoSource, NotRequester, NotDJorStaff, GenericError, \
    MissingVoicePerms, DiffVoiceChannel
from .models import LavalinkPlayer
from ..db import DBModel

if TYPE_CHECKING:
    from ..client import BotCore
    from ..others import CustomContext


def can_send_message(channel: Union[disnake.TextChannel, disnake.VoiceChannel, disnake.Thread], bot: disnake.Member):
    if not channel.permissions_for(bot).send_messages:
        raise GenericError(f"**Não tenho permissão de enviar mensagens no canal:** {channel.mention}")

    if not channel.permissions_for(bot).embed_links:
        raise GenericError(f"**Não tenho permissão de inserir links no canal: {channel.mention}**")

    return True


async def check_requester_channel(ctx: CustomContext):

    guild_data = await ctx.bot.get_data(ctx.guild.id, db_name=DBModel.guilds)

    if guild_data['player_controller']["channel"] == str(ctx.channel.id):
        raise GenericError("**Não use comandos neste canal!**", self_delete=True, delete_original=15)

    return True


async def check_pool_bots(inter, only_voiced: bool = False):

    try:
        inter.music_bot
        return True
    except AttributeError:
        pass

    if isinstance(inter, (disnake.MessageInteraction, disnake.ModalInteraction)):
        return False

    free_bot = None

    for bot in inter.bot.pool.bots:

        if bot.user.id in inter.author.voice.channel.voice_states:
            inter.music_bot = bot
            inter.music_guild = bot.get_guild(inter.guild.id)
            return True

        if inter.bot.user.id == bot.user.id:
            continue

        if only_voiced:
            continue

        if not (guild := bot.get_guild(inter.guild.id)):
            continue

        if not guild.voice_client:
            free_bot = bot, guild

    if not inter.guild.voice_client:
        inter.music_bot = inter.bot
        inter.music_guild = inter.guild
        return True

    if free_bot:
        inter.music_bot, inter.music_guild = free_bot
        return True

    txt = ""

    extra_bots_invite = []

    for bot in inter.bot.pool.bots:

        if bot.user == inter.bot.user or not bot.public or bot.get_guild(inter.guild.id):
            continue

        extra_bots_invite.append(f"[`{disnake.utils.escape_markdown(str(bot.user)).replace(' ', '_')}`]({disnake.utils.oauth_url(bot.user.id, permissions=disnake.Permissions(bot.config['INVITE_PERMISSIONS']), scopes=('bot', 'applications.commands'))})")

    txt += " | ".join(extra_bots_invite)

    if txt:
        txt = f"\n\nVocê pode convidar bots adicionais no seu servidor através dos links abaixo:\n{txt}"

    raise GenericError(f"**Não há bots livre no momento...**{txt}")

def has_player(check_all_bots: bool = False):

    async def predicate(inter):

        if check_all_bots and inter.bot.intents.members:

            try:
                await check_pool_bots(inter, only_voiced=True)
                bot = inter.music_bot
            except AttributeError:
                raise GenericError("Não há player ativo no momento...")

        else:

            try:
                bot = inter.music_bot
            except AttributeError:
                bot = inter.bot

        try:
            bot.music.players[inter.guild.id]
        except KeyError:
            raise NoPlayer()

        return True

    return commands.check(predicate)


def is_dj():

    async def predicate(inter):

        if inter.bot.intents.members:
            await check_pool_bots(inter, only_voiced=True)

        if not await has_perm(inter):
            raise NotDJorStaff()

        return True

    return commands.check(predicate)


def can_send_message_check():

    async def predicate(inter):
        # adaptar pra checkar outros bots
        can_send_message(inter.channel, inter.guild.me)
        return True

    return commands.check(predicate)


def is_requester():

    async def predicate(inter):

        try:
            bot = inter.music_bot
        except AttributeError:
            if not inter.bot.intents.members:
                bot = inter.bot
            else:
                try:
                    await check_pool_bots(inter, only_voiced=True)
                    bot = inter.music_bot
                except AttributeError:
                    bot = inter.bot

        try:
            player: LavalinkPlayer = bot.music.players[inter.guild.id]
        except KeyError:
            raise NoPlayer()

        if not player.current:
            raise NoSource()

        if player.current.requester == inter.author.id or not (player.keep_connected or player.restrict_mode):
            return True

        try:
            if await has_perm(inter):
                return True

        except NotDJorStaff:
            pass

        raise NotRequester()

    return commands.check(predicate)


def check_voice(bot_is_connected=False):

    async def predicate(inter):

        if not inter.author.voice:
            raise NoVoice()

        try:
            guild = inter.music_guild
        except AttributeError:
            guild = inter.guild

        if inter.bot.intents.members:

            if await check_pool_bots(inter, only_voiced=bot_is_connected):
                return True

        if not guild.me.voice:

            perms = inter.author.voice.channel.permissions_for(guild.me)

            if not perms.connect:
                raise MissingVoicePerms(inter.author.voice.channel)

        try:
            if inter.author.id not in guild.me.voice.channel.voice_states:
                raise DiffVoiceChannel()
        except AttributeError:
            pass

        return True

    return commands.check(predicate)


def has_source():

    async def predicate(inter):

        try:
            bot = inter.music_bot
        except AttributeError:
            if not inter.bot.intents.members:
                bot = inter.bot
            else:
                try:
                    await check_pool_bots(inter, only_voiced=True)
                    bot = inter.music_bot
                except AttributeError:
                    bot = inter.bot

        try:
            player = bot.music.players[inter.guild.id]
        except KeyError:
            raise NoPlayer()

        if not player.current:
            raise NoSource()

        return True

    return commands.check(predicate)


def user_cooldown(rate: int, per: int):
    def custom_cooldown(inter: disnake.Interaction):
        # if (await inter.bot.is_owner(inter.author)):
        #   return None  # sem cooldown

        return commands.Cooldown(rate, per)

    return custom_cooldown


#######################################################################


async def has_perm(inter):

    try:
        bot = inter.music_bot
        guild = inter.music_guild
        channel = guild.get_channel(inter.channel.id)
        author = guild.get_member(inter.author.id)
    except AttributeError:
        bot = inter.bot
        guild = inter.guild
        channel = inter.channel
        author = inter.author

    try:
        player: LavalinkPlayer = bot.music.players[inter.guild.id]
    except KeyError:
        return True

    if author.id in player.dj:
        return True

    if author.guild_permissions.manage_channels:
        return True

    if player.keep_connected:
        raise GenericError(f"**Erro!** Apenas membros com a permissão de **gerenciar servidor** "
                           "podem usar este comando/botão com o **modo 24/7 ativo**...")

    user_roles = [r.id for r in author.roles]

    guild_data = await bot.get_data(guild.id, db_name=DBModel.guilds)

    if [r for r in guild_data['djroles'] if int(r) in user_roles]:
        return True

    if player.restrict_mode:
        raise GenericError(f"**Erro!** Apenas DJ's ou membros com a permissão de **gerenciar servidor** "
                           "podem usar este comando/botão com o **modo restrito ativo**...")

    vc = bot.get_channel(player.channel_id)

    if not vc and author.voice:
        player.dj.add(author.id)

    elif bot.intents.members and not [m for m in vc.members if
                                            not m.bot and (m.guild_permissions.manage_channels or m.id in player.dj)]:
        player.dj.add(author.id)
        await channel.send(embed=disnake.Embed(
            description=f"{author.mention} foi adicionado à lista de DJ's por não haver um no canal <#{vc.id}>.",
            color=player.bot.get_color(guild.me)), delete_after=10)
        return True


def can_connect(
        channel: Union[disnake.VoiceChannel, disnake.StageChannel],
        guild: disnake.Guild,
        bot: BotCore,
        check_other_bots_in_vc: bool = False,
        check_pool: bool = False
):

    perms = channel.permissions_for(guild.me)

    if not perms.connect:
        raise GenericError(f"**Não tenho permissão para conectar no canal {channel.mention}**")

    if not isinstance(channel, disnake.StageChannel):

        if not perms.speak:
            raise GenericError(f"**Não tenho permissão para falar no canal {channel.mention}**")

        if not guild.voice_client and channel.user_limit and (guild.me.id not in channel.voice_states and (channel.user_limit - len(channel.voice_states)) < 1):
            raise GenericError(f"**O canal {channel.mention} está lotado!**")

    if check_other_bots_in_vc and any(m for m in channel.members if m.bot and m.id != guild.me.id):
        raise GenericError(f"**Há outro bot conectado no canal:** <#{channel.id}>")

    if check_pool:

        for b in bot.pool.bots:

            if b.user.id == bot.user.id:
                continue

            if b.user.id in channel.voice_states:
                raise GenericError(f"**<@{b.user.id}> já está em uso no canal** <#{channel.id}>")

async def check_deafen(me: disnake.Member = None):

    if me.voice.deaf:
        return True
    elif me.guild_permissions.deafen_members:
        try:
            await me.edit(deafen=True)
            return True
        except:
            traceback.print_exc()
