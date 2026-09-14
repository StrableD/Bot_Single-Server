import discord
from discord import app_commands
from discord.ext.commands import Cog
from sqlalchemy import select

from lib.bot import My_Bot
from lib.db import db
from lib.db.cadre_db import getCurrentGameCadre
from lib.db.models import Lobby, LobbyPlayer, Player
from lib.helper.checks import app_is_gamemaster

# --- UI Views ---


class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: int):
        super().__init__(timeout=None)
        self.lobby_id = lobby_id

    @discord.ui.button(
        label="Join Match", style=discord.ButtonStyle.green, custom_id="lobby_join"
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with db.AsyncSessionLocal() as session:
            lobby = await session.get(Lobby, self.lobby_id)
            if not lobby or not lobby.is_active:
                await interaction.response.send_message(
                    "This lobby is closed.", ephemeral=True
                )
                return

            result = await session.execute(
                select(LobbyPlayer).where(
                    LobbyPlayer.lobby_id == self.lobby_id,
                    LobbyPlayer.player_id == interaction.user.id,
                )
            )
            if result.scalar_one_or_none():
                await interaction.response.send_message(
                    "You have already joined!", ephemeral=True
                )
                return

            lp = LobbyPlayer(lobby_id=self.lobby_id, player_id=interaction.user.id)
            session.add(lp)
            await session.commit()

            # Update embed
            players = await session.execute(
                select(LobbyPlayer.player_id).where(
                    LobbyPlayer.lobby_id == self.lobby_id
                )
            )
            player_ids = [p[0] for p in players.fetchall()]

            embed = interaction.message.embeds[0]
            embed.set_field_at(
                0, name="Players Joined", value=f"{len(player_ids)}", inline=False
            )
            embed.set_field_at(
                1,
                name="Player List",
                value="\n".join([f"<@{pid}>" for pid in player_ids]) or "None",
                inline=False,
            )

            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Start Match", style=discord.ButtonStyle.primary, custom_id="lobby_start"
    )
    async def start_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with db.AsyncSessionLocal() as session:
            lobby = await session.get(Lobby, self.lobby_id)
            if not lobby or not lobby.is_active:
                await interaction.response.send_message(
                    "This lobby is already closed or invalid.", ephemeral=True
                )
                return

            if (
                interaction.user.id != lobby.gamemaster_id
                and interaction.user.id != interaction.guild.owner_id
            ):
                await interaction.response.send_message(
                    "Only the Gamemaster who created the lobby can start it.",
                    ephemeral=True,
                )
                return

            # Check if cadre matches player count
            players = await session.execute(
                select(LobbyPlayer.player_id).where(
                    LobbyPlayer.lobby_id == self.lobby_id
                )
            )
            player_ids = [p[0] for p in players.fetchall()]

            cadre = await getCurrentGameCadre()
            # Simple check for now
            cadre_length = sum(cadre.values()) if cadre else 0

            if len(player_ids) < cadre_length:
                await interaction.response.send_message(
                    f"Not enough players! Have {len(player_ids)}, need {cadre_length}.",
                    ephemeral=True,
                )
                return
            elif len(player_ids) > cadre_length:
                await interaction.response.send_message(
                    f"Too many players! Have {len(player_ids)}, need {cadre_length}.",
                    ephemeral=True,
                )
                return

            lobby.is_active = False
            await session.commit()

            # Disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content="Match is starting...", view=self
            )

            # To-Do: Assign roles, move to voice channels

    @discord.ui.button(
        label="Cancel Lobby", style=discord.ButtonStyle.danger, custom_id="lobby_cancel"
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with db.AsyncSessionLocal() as session:
            lobby = await session.get(Lobby, self.lobby_id)
            if not lobby or not lobby.is_active:
                await interaction.response.send_message(
                    "This lobby is already closed or invalid.", ephemeral=True
                )
                return

            if (
                interaction.user.id != lobby.gamemaster_id
                and interaction.user.id != interaction.guild.owner_id
            ):
                await interaction.response.send_message(
                    "Only the Gamemaster who created the lobby can cancel it.",
                    ephemeral=True,
                )
                return

            lobby.is_active = False
            await session.commit()

            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content="❌ Lobby cancelled by Gamemaster.", embed=None, view=self
            )


# --- Cog ---


class Game(Cog):
    def __init__(self, bot: My_Bot):
        self.bot = bot

    game_group = app_commands.Group(name="game", description="Game commands")
    gm_group = app_commands.Group(name="gm", description="Gamemaster commands")

    @game_group.command(name="join", description="Join an active game lobby")
    async def game_join(self, interaction: discord.Interaction):
        async with db.AsyncSessionLocal() as session:
            result = await session.execute(select(Lobby).where(Lobby.is_active))
            lobby = result.scalar_one_or_none()

            if not lobby:
                await interaction.response.send_message(
                    "There is no active lobby right now.", ephemeral=True
                )
                return

            res_lp = await session.execute(
                select(LobbyPlayer).where(
                    LobbyPlayer.lobby_id == lobby.id,
                    LobbyPlayer.player_id == interaction.user.id,
                )
            )
            if res_lp.scalar_one_or_none():
                await interaction.response.send_message(
                    "You are already in the lobby.", ephemeral=True
                )
                return

            session.add(LobbyPlayer(lobby_id=lobby.id, player_id=interaction.user.id))
            await session.commit()

            await interaction.response.send_message(
                "You have joined the lobby!", ephemeral=True
            )

    @game_group.command(
        name="action",
        description="Submit a role action (e.g. Seer inspect, Werewolf vote)",
    )
    async def game_action(
        self, interaction: discord.Interaction, target: discord.Member, action_name: str
    ):
        from lib.db.models import ActionRequest

        async with db.AsyncSessionLocal() as session:
            result = await session.execute(select(Lobby).where(Lobby.is_active))
            lobby = result.scalar_one_or_none()
            if not lobby:
                await interaction.response.send_message(
                    "No active game to submit actions to.", ephemeral=True
                )
                return

            req = ActionRequest(
                lobby_id=lobby.id,
                player_id=interaction.user.id,
                action_type=action_name,
                target_id=target.id,
            )
            session.add(req)
            await session.commit()

        await interaction.response.send_message(
            f"Action '{action_name}' targeting {target.display_name} sent to GM for approval.",
            ephemeral=True,
        )

    @game_group.command(
        name="current_cadre", description="View the current active game cadre"
    )
    async def game_current_cadre(self, interaction: discord.Interaction):
        cadre = await getCurrentGameCadre()
        if not cadre:
            await interaction.response.send_message(
                "No active cadre set.", ephemeral=True
            )
            return

        desc = "\n".join([f"{k}: {v}" for k, v in cadre.items()])
        embed = discord.Embed(
            title="Current Cadre", description=desc, color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @gm_group.command(name="start", description="Open a game lobby")
    async def gm_start(self, interaction: discord.Interaction):
        # Allow server owner or gamemaster
        try:
            gm_id = await db.getRoleID("gamemaster")
            is_gm = any(r.id == gm_id for r in interaction.user.roles)
        except ValueError:
            is_gm = False

        if not is_gm and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You don't have permission.", ephemeral=True
            )
            return

        async with db.AsyncSessionLocal() as session:
            # Check for existing lobby
            res = await session.execute(select(Lobby).where(Lobby.is_active))
            if res.scalar_one_or_none():
                await interaction.response.send_message(
                    "An active lobby already exists!", ephemeral=True
                )
                return

            cadre = await getCurrentGameCadre()
            cadre_length = sum(cadre.values()) if cadre else 0

            lobby = Lobby(gamemaster_id=interaction.user.id)
            session.add(lobby)
            await session.commit()

            embed = discord.Embed(
                title="Game Lobby Open!",
                description="Click to join the match.",
                color=discord.Color.green(),
            )
            embed.add_field(name="Players Joined", value="0", inline=False)
            embed.add_field(name="Player List", value="None", inline=False)
            embed.add_field(
                name="Required Cadre Size", value=str(cadre_length), inline=False
            )
            embed.set_footer(text=f"Gamemaster: {interaction.user.display_name}")

            view = LobbyView(lobby_id=lobby.id)
            await interaction.response.send_message(embed=embed, view=view)

    @gm_group.command(
        name="stop", description="Stop the game, calculate Elo, and chronicle"
    )
    @app_is_gamemaster()
    @app_commands.choices(
        winner=[
            app_commands.Choice(name="Dorf", value="dorf"),
            app_commands.Choice(name="Werwölfe", value="werwolf"),
            app_commands.Choice(name="Liebespaar", value="liebespaar"),
            app_commands.Choice(name="Niemand", value="niemand"),
        ]
    )
    async def gm_stop(
        self, interaction: discord.Interaction, winner: app_commands.Choice[str]
    ):
        await interaction.response.defer(ephemeral=False)
        async with db.AsyncSessionLocal() as session:
            res = await session.execute(select(Lobby).where(Lobby.is_active))
            lobby = res.scalar_one_or_none()
            if not lobby:
                await interaction.followup.send(
                    "There is no active game lobby to stop.", ephemeral=True
                )
                return

            lobby.is_active = False

            # Evaluate Elo
            lps_res = await session.execute(
                select(LobbyPlayer).where(LobbyPlayer.lobby_id == lobby.id)
            )
            lobby_players = lps_res.scalars().all()

            # Very basic team classification
            werewolf_roles = {
                "Werwolf-1",
                "Werwolf-2",
                "Polarwolf",
                "Wolfsseher",
                "Werwolfjunges",
                "Weißer-Werwolf",
                "Werschweinchen",
            }

            for lp in lobby_players:
                player = await session.get(Player, lp.player_id)
                if not player:
                    player = Player(
                        PlayerId=lp.player_id,
                        PlayerName="Unknown",
                        Elo=1300,
                        PlayedGamesComplete=0,
                        WonGamesComplete=0,
                        PlayedGamesSeason=0,
                        WonGamesSeason=0,
                    )
                    session.add(player)

                player.PlayedGamesComplete = (player.PlayedGamesComplete or 0) + 1
                player.PlayedGamesSeason = (player.PlayedGamesSeason or 0) + 1

                # Determine win
                is_win = False
                if winner.value == "werwolf":
                    is_win = lp.role in werewolf_roles
                elif winner.value == "dorf":
                    is_win = lp.role not in werewolf_roles and lp.role is not None
                elif winner.value == "liebespaar":
                    pass  # Handled differently, or we assume Amor/Lovers logic here. For now we just don't grant it to generic roles.

                if is_win:
                    player.WonGamesComplete = (player.WonGamesComplete or 0) + 1
                    player.WonGamesSeason = (player.WonGamesSeason or 0) + 1
                    player.Elo = (player.Elo or 1300) + 20
                else:
                    player.Elo = (player.Elo or 1300) - 10

            await session.commit()

        await interaction.followup.send(
            f"Game stopped. Winner: {winner.name}. Elo calculated.",
            ephemeral=False,
        )

    @gm_group.command(name="phase", description="Manually transition the game phase")
    @app_commands.choices(
        phase=[
            app_commands.Choice(name="Night", value="night"),
            app_commands.Choice(name="Day", value="day"),
            app_commands.Choice(name="Voting", value="voting"),
        ]
    )
    async def gm_phase(
        self, interaction: discord.Interaction, phase: app_commands.Choice[str]
    ):
        await interaction.response.send_message(
            f"Transitioning to {phase.name} phase... Prompting players for actions.",
            ephemeral=True,
        )


async def setup(bot: My_Bot):
    await bot.add_cog(Game(bot))
