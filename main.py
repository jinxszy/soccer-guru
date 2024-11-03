import discord
from discord.ext import commands
import logging
from flask import Flask, render_template, request, redirect, flash, url_for
from datetime import datetime
import threading
import asyncio
import config  # Ensure you have your config file with your TOKEN and other constants
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(file_handler)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure random key

# Discord bot setup
class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="?", intents=intents, help_command=None)

    async def on_ready(self):
        logging.info(f'Logged in as: {self.user.name} (ID: {self.user.id})')
        await guild_manager.update_channels()  # Update channels when the bot is ready

class GuildManager:
    def __init__(self, bot):
        self.bot = bot
        self.guild_channels = {}

    async def update_channels(self):
        for guild in self.bot.guilds:
            self.guild_channels[guild.id] = [channel.name for channel in guild.text_channels if channel.type == discord.ChannelType.text]
            logging.info(f"Available channels in {guild.name}: {self.guild_channels[guild.id]}")

bot = Bot()
guild_manager = GuildManager(bot)

# Ticket management data
tickets_data = {
    "ticket_number": 1,
}

class TicketButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Set timeout to None for persistence
        close_ticket_button = discord.ui.Button(label="Close Ticket", style=discord.ButtonStyle.red)
        close_ticket_button.callback = self.close_ticket  # Set the callback method
        self.add_item(close_ticket_button)

    async def close_ticket(self, interaction: discord.Interaction):
        try:
            logging.info(f"{interaction.user} clicked 'Close Ticket' in {interaction.channel}.")
            channel = discord.utils.get(interaction.guild.text_channels, id=interaction.channel.id)
            if channel and interaction.channel.category and interaction.channel.category.name == "Tickets":
                await channel.delete()
            else:
                await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        except Exception as e:
            logging.error(f"Error in close_ticket button: {e}")
            await interaction.response.send_message("Error closing the ticket. Try again later.", ephemeral=True)

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support", value="general"),
            discord.SelectOption(label="Billing", value="billing"),
            discord.SelectOption(label="Technical Support", value="technical"),
        ]
        super().__init__(placeholder="Select ticket type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        global tickets_data
        ticket_number = tickets_data["ticket_number"]
        channel_name = f'ticket-{ticket_number:04}'
        tickets_data["ticket_number"] += 1

        # Ensure a 'Tickets' category exists
        category = discord.utils.get(interaction.guild.categories, name='Tickets')
        if category is None:
            await interaction.response.send_message("Ticket category not found. Please create a 'Tickets' category.", ephemeral=True)
            return

        try:
            # Create the ticket channel
            channel = await category.create_text_channel(channel_name)
            await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await channel.set_permissions(interaction.guild.default_role, read_messages=False)

            # Create the ticket embed
            embed = discord.Embed(
                title="Ticket Opened",
                description=f"Ticket opened by {interaction.user.mention} for {self.values[0]}. Please describe your issue.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )

            # Create a view with buttons to close the ticket
            view = TicketButtons()  
            await channel.send(embed=embed, view=view)

            # Acknowledge ticket creation to the user
            await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)
        except Exception as e:
            logging.error(f"Failed to create ticket channel: {e}")
            await interaction.response.send_message("There was an error creating your ticket. Please try again later.", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@app.route('/')
def index():
    return redirect('/ticket-panel')

@app.route('/ticket-panel', methods=['GET', 'POST'])
def ticket_panel():
    channels = []

    if request.method == 'POST':
        try:
            channel_name = request.form['channel']  # Get the specified channel name
            embed_title = request.form['embed_title']  # Get the embed title
            embed_description = request.form['embed_description']  # Get the embed description
            embed_color = request.form['embed_color'].lstrip('#')
            embed_footer = request.form['embed_footer']  # Remove '#' from color input
            footer_url = request.form['footer_url']
            embed_author = request.form['embed_author']
            embed_author_url = request.form['embed_author_url']
            embed_image = request.form['embed_image']
            logging.info(f"Received request to send ticket panel to channel name: {channel_name}")

            channel = None
            for guild in bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    break  # Stop searching if the channel is found

            if channel:
                # Create an embed with the provided details
                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=int(embed_color, 16)  # Convert the color string to an integer
                )
                embed.set_author(name=f'{embed_author}', icon_url=embed_author_url)
                embed.set_footer(text=f"{embed_footer}", icon_url=footer_url)
                embed.set_thumbnail(url=bot.user.avatar.url)
                embed.timestamp = discord.utils.utcnow()  # Set the timestamp to now
                embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url)
                embed.set_image(url=embed_image)
                # Send the ticket panel asynchronously
                asyncio.run_coroutine_threadsafe(send_ticket_panel(channel, embed), bot.loop)
                flash(f"The ticket panel has been sent to #{channel_name}.", "success")
            else:
                flash("Channel not found.", "error")
                logging.error(f"Channel '{channel_name}' not found in any guild.")

        except ValueError as ve:
            logging.error(f"Invalid input: {ve}")
            flash("Please make sure all inputs are valid.", "error")
        except Exception as e:
            logging.error(f"Error processing ticket panel request: {e}")
            flash("An error occurred while sending the ticket panel. Please try again.", "error")

        return redirect(url_for('ticket_panel'))

    # Populate channels for all guilds for the GET request
    channels = [channel.name for guild in bot.guilds for channel in guild.text_channels]

    return render_template('ticket_panel.html', channels=channels)


async def send_ticket_panel(channel, embed):
    try:
        view = TicketView()  # Create an instance of TicketView
        await channel.send(embed=embed, view=view)
    except Exception as e:
        logging.error(f"Error sending ticket panel: {e}")

def run_flask():
    app.run(port=5000, debug=True, use_reloader=False)

async def load_cogs(bot):
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
            except Exception as e:
                logging.error(f'Failed to load cog {filename[:-3]}: {e}')

async def main():
    try:
        # Start the Flask app in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()
        await load_cogs(bot)
        await bot.start(config.TOKEN)  # Replace with your actual token
    except Exception as e:
        logging.error(f"Error during bot initialization: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
