import itertools
from utils.music.models import LavalinkPlayer
import disnake
from utils.music.converters import time_format, fix_characters, get_button_style
from utils.others import PlayerControls


class MiniSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = "mini"
        self.preview = "https://cdn.discordapp.com/attachments/554468640942981147/1047184549790101574/skin_mini.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = True
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:

        data = {
            "content": None,
            "embeds": [],
        }

        embed_color = player.bot.get_color(player.guild.me)

        embed = disnake.Embed(
            color=embed_color,
            description=f"[`{player.current.single_title}`]({player.current.uri})"
        )
        embed_queue = None
        queue_size = len(player.queue)

        if not player.paused:
            embed.set_author(
                name="Trenutno:",
                icon_url="https://media.discordapp.net/attachments/480195401543188483/987633257178882108/Equalizer.gif",
            )

        else:
            embed.set_author(
                name="Na pauzi:",
                icon_url="https://cdn.discordapp.com/attachments/480195401543188483/896013933197013002/pause.png"
            )

        if player.current.track_loops:
            embed.description += f" `[🔂 {player.current.track_loops}]`"

        elif player.loop:
            if player.loop == 'current':
                embed.description += ' `[🔂 aktuelnu muziku]`'
            else:
                embed.description += ' `[🔁 linija]`'

        embed.description += f" `[`<@{player.current.requester}>`]`"

        duration = "🔴 Livestream" if player.current.is_stream else \
            time_format(player.current.duration)

        embed.add_field(name="⏰ **⠂Trajanje:**", value=f"```ansi\n[34;1m{duration}[0m\n```")
        embed.add_field(name="💠 **⠂Uploader/Artista:**",
                        value=f"```ansi\n[34;1m{fix_characters(player.current.author, 18)}[0m\n```")

        if player.command_log:
            embed.add_field(name=f"{player.command_log_emoji} **⠂Zadnja interakcija:**",
                            value=f"{player.command_log}", inline=False)

        if queue_size:

            embed.description += f" `({queue_size})`"

            if player.mini_queue_enabled:
                embed_queue = disnake.Embed(
                    color=embed_color,
                    description="\n".join(
                        f"`{(n + 1):02}) [{time_format(t.duration) if not t.is_stream else '🔴 Livestream'}]` [`{fix_characters(t.title, 38)}`]({t.uri})"
                        for n, t in (enumerate(itertools.islice(player.queue, 5)))
                    )
                )
                embed_queue.set_image(url="https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif")

        embed.set_thumbnail(url=player.current.thumb)
        embed.set_image(url="https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif")

        if player.current_hint:
            embed.set_footer(text=f"💡 Savjet: {player.current_hint}")

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

        data["components"] = [
            disnake.ui.Button(emoji="⏯️", custom_id=PlayerControls.pause_resume, style=get_button_style(player.paused)),
            disnake.ui.Button(emoji="⏮️", custom_id=PlayerControls.back),
            disnake.ui.Button(emoji="⏹️", custom_id=PlayerControls.stop),
            disnake.ui.Button(emoji="⏭️", custom_id=PlayerControls.skip),
            disnake.ui.Button(emoji="📑", custom_id=PlayerControls.queue),
            disnake.ui.Select(
                placeholder="Više mogućnosti:",
                custom_id="musicplayer_dropdown_inter",
                min_values=0, max_values=1,
                options=[
                    disnake.SelectOption(
                        label="Dodati glazbu", emoji="<:add_music:588172015760965654>",
                        value=PlayerControls.add_song,
                        description="Dodajte pjesmu/popis za reprodukciju u red čekanja."
                    ),
                    disnake.SelectOption(
                        label="Dodaj favorit", emoji="⭐",
                        value=PlayerControls.enqueue_fav,
                        description="Dodajte jedan od svojih favorita u red čekanja."
                    ),
                    disnake.SelectOption(
                        label="Igrati od početka", emoji="⏪",
                        value=PlayerControls.seek_to_start,
                        description="Vraćanje tempa trenutne pjesme na početak."
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

        if player.mini_queue_feature:
            data["components"][5].options.append(
                disnake.SelectOption(
                    label="Mini player", emoji="<:music_queue:703761160679194734>",
                    value=PlayerControls.miniqueue,
                    description="Omogući/onemogući mini-red igrača."
                )
            )

        return data

def load():
    return MiniSkin()
