import datetime
from utils.music.models import LavalinkPlayer
import disnake
from utils.music.converters import fix_characters, time_format, get_button_style
import itertools
from utils.others import PlayerControls


class DefaultStaticSkin:
    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = "default_static"
        self.preview = "https://cdn.discordapp.com/attachments/554468640942981147/1047187412666810448/default_static_skin.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = True

    def load(self, player: LavalinkPlayer) -> dict:

        data = {
            "content": None,
            "embeds": []
        }

        embed = disnake.Embed(color=player.bot.get_color(player.guild.me))
        embed_queue = None
        vc_txt = ""

        if not player.paused:
            embed.set_author(
                name="Trenutno:",
                icon_url="https://cdn.discordapp.com/attachments/480195401543188483/895862881105616947/music_equalizer.gif"
            )

        else:
            embed.set_author(
                name="Na pauzi:",
                icon_url="https://cdn.discordapp.com/attachments/480195401543188483/896013933197013002/pause.png"
            )

        if player.current_hint:
            embed.set_footer(text=f"💡 Dica: {player.current_hint}")
        elif player.node.identifier != "LOCAL":
            embed.set_footer(
                text=str(player),
                icon_url="https://cdn.discordapp.com/attachments/480195401543188483/907119505971486810/speaker-loud-speaker.gif"
            )

        queue_img = ""

        try:
            vc_txt = f"\n> *️⃣ **⠂U kanalu:** {player.guild.me.voice.channel.mention}"
        except AttributeError:
            pass

        duration = "> 🔴 **⠂Trajanje:** `Livestream`" if player.current.is_stream else \
            (f"> ⏰ **⠂Trajanje:** `{time_format(player.current.duration)} [`" +
            f"<t:{int((disnake.utils.utcnow() + datetime.timedelta(milliseconds=player.current.duration - player.position)).timestamp())}:R>`]`"
            if not player.paused else '')

        txt = f"[`{player.current.single_title}`]({player.current.uri})\n\n" \
              f"{duration}\n" \
              f"> 💠 **⠂Od:** {player.current.authors_md}\n" \
              f"> ✋ **⠂Zahtjev od:** <@{player.current.requester}>\n" \
              f"> 🔊 **⠂Glasnoća:** `{player.volume}%`"

        if player.current.track_loops:
            txt += f"\n> 🔂 **⠂Preostalih ponavljanja:** `{player.current.track_loops}`"

        if player.loop:
            if player.loop == 'current':
                e = '🔂'; m = 'Aktuelnu muziku'
            else:
                e = '🔁'; m = 'Fila'
            txt += f"\n> {e} **⠂Režim ponavljanja:** `{m}`"

        if player.nightcore:
            txt += f"\n> 🇳 **⠂Nightcore efekat:** `ativado`"

        if player.current.album_name:
            txt += f"\n> 💽 **⠂Album:** [`{fix_characters(player.current.album_name, limit=20)}`]({player.current.album_url})"

        if player.current.playlist_name:
            txt += f"\n> 📑 **⠂Playlist:** [`{fix_characters(player.current.playlist_name, limit=20)}`]({player.current.playlist_url})"

        if player.keep_connected:
            txt += "\n> ♾️ **⠂Mod 24/7:** `Ativado`"

        elif player.restrict_mode:
            txt += f"\n> 🔒 **⠂Modo restrikcija:** `Ativado`"

        txt += f"{vc_txt}\n"

        if player.command_log:
            txt += f"```ansi\n [34;1mÚltima Interação[0m```**┕ {player.command_log_emoji} ⠂**{player.command_log}\n"

        if qlenght:=len(player.queue):

            queue_txt = "\n".join(
                f"`{(n + 1):02}) [{time_format(t.duration) if not t.is_stream else '🔴 Livestream'}]` [`{fix_characters(t.title, 33)}`]({t.uri})"
                for n, t in (enumerate(itertools.islice(player.queue, 20)))
            )

            embed_queue = disnake.Embed(title=f"Pesme u redu: {qlenght}", color=player.bot.get_color(player.guild.me),
                                        description=f"\n{queue_txt}")

            if not player.loop and not player.keep_connected and not player.paused and not player.current.is_stream:

                queue_duration = 0

                for t in player.queue:
                    if not t.is_stream:
                        queue_duration += t.duration

                embed_queue.description += f"\n`[⌛ Pesme se završavaju` <t:{int((disnake.utils.utcnow() + datetime.timedelta(milliseconds=(queue_duration + (player.current.duration if not player.current.is_stream else 0)) - player.position)).timestamp())}:R> `⌛]`"

            embed_queue.set_image(url=queue_img)

        embed.description = txt

        embed.set_image(url=player.current.thumb or "https://media.discordapp.net/attachments/480195401543188483/987830071815471114/musicequalizer.gif")

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

        data["components"] = [
            disnake.ui.Button(emoji="⏯️", custom_id=PlayerControls.pause_resume, style=get_button_style(player.paused)),
            disnake.ui.Button(emoji="⏮️", custom_id=PlayerControls.back),
            disnake.ui.Button(emoji="⏹️", custom_id=PlayerControls.stop),
            disnake.ui.Button(emoji="⏭️", custom_id=PlayerControls.skip),
            disnake.ui.Button(emoji="📑", custom_id=PlayerControls.queue),
            disnake.ui.Select(
                placeholder="Više opcija:",
                custom_id="musicplayer_dropdown_inter",
                min_values=0, max_values=1,
                options=[
                    disnake.SelectOption(
                        label= "Dodati muziku", emoji="<:add_music:588172015760965654>",
                        value=PlayerControls.add_song,
                        description="Dodajte pjesmu/listu za reprodukciju u red čekanja."
                    ),
                    disnake.SelectOption(
                        label="Dodati favorit", emoji="⭐",
                        value=PlayerControls.enqueue_fav,
                        description="Dodajte jednog od svojih favorita u red čekanja."
                    ),
                    disnake.SelectOption(
                        label="Pusti od početka", emoji="⏪",
                        value=PlayerControls.seek_to_start,
                        description="Vratite tempo trenutne pjesme na početak."
                    ),
                    disnake.SelectOption(
                        label="Glasnoća", emoji="🔊",
                        value=PlayerControls.volume,
                        description="Podesite jačinu zvuka."
                    ),
                    disnake.SelectOption(
                        label="Mix", emoji="🔀",
                        value=PlayerControls.shuffle,
                        description="Miks pjesama u redu."
                    ),
                    disnake.SelectOption(
                        label="Urednik", emoji="🎶",
                        value=PlayerControls.readd,
                        description="Ponovo dodajte reprodukovane pesme u red čekanja."
                    ),
                    disnake.SelectOption(
                        label="Ponavljanje", emoji="🔁",
                        value=PlayerControls.loop_mode,
                        description="Omogući/onemogući ponavljanje pjesme/reda."
                    ),
                    disnake.SelectOption(
                        label="Nightcore", emoji="🇳",
                        value=PlayerControls.nightcore,
                        description="Omogući/onemogući noćni efekat."
                    ),
                    disnake.SelectOption(
                        label="Omogući/onemogući ograničeni način rada", emoji="🔐",
                        value=PlayerControls.restrict_mode,
                        description="Samo DJ-i/osoblje mogu koristiti ograničene komande."
                    ),
                ]
            ),
        ]

        return data

def load():
    return DefaultStaticSkin()
