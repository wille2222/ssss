import os
import sqlite3
import discord
from discord.ext import commands
from typing import Final
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')

# Initialize bot with intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Database file
DB_FILE = 'god_studio_bot.db'

def init_db():
    """Initialize the database with the required tables."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                guild_id INTEGER,
                role_id INTEGER,
                permissions TEXT,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS info_roles (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS info_members (
                guild_id INTEGER,
                member_id INTEGER,
                PRIMARY KEY (guild_id, member_id)
            )
        ''')
        conn.commit()

def set_role_permissions(guild_id: int, role_id: int, permissions: str):
    """Set the permissions for a role in the database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO role_permissions (guild_id, role_id, permissions)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, role_id) DO UPDATE SET permissions = excluded.permissions
        ''', (guild_id, role_id, permissions))
        conn.commit()

def get_role_permissions(guild_id: int, role_id: int) -> str:
    """Get the permissions for a role from the database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT permissions FROM role_permissions WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
        result = cursor.fetchone()
        return result[0] if result else ''

def set_info_role(guild_id: int, role_id: int):
    """Set a role that can use the !info command."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO info_roles (guild_id, role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, role_id) DO NOTHING
        ''', (guild_id, role_id))
        conn.commit()

def add_info_member(guild_id: int, member_id: int):
    """Add a member to the list of those who can use the !info command."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO info_members (guild_id, member_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, member_id) DO NOTHING
        ''', (guild_id, member_id))
        conn.commit()

def remove_info_member(guild_id: int, member_id: int):
    """Remove a member from the list of those who can use the !info command."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM info_members WHERE guild_id = ? AND member_id = ?', (guild_id, member_id))
        conn.commit()

def is_authorized(ctx: commands.Context) -> bool:
    """Check if the user is authorized to use the !info command."""
    guild_id = ctx.guild.id
    member = ctx.author
    # Check if the member is the server owner
    if member.id == ctx.guild.owner_id:
        return True
    # Check if the member has a role with info permissions
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM info_roles WHERE guild_id = ? AND role_id IN (SELECT role_id FROM members_roles WHERE member_id = ?)', (guild_id, member.id))
        if cursor.fetchone():
            return True
        # Check if the member has been individually granted !info permissions
        cursor.execute('SELECT 1 FROM info_members WHERE guild_id = ? AND member_id = ?', (guild_id, member.id))
        if cursor.fetchone():
            return True
    return False

def has_mod_permissions(ctx: commands.Context) -> bool:
    """Check if the user has mod permissions."""
    member = ctx.author
    # Check if the member has a role with admin permissions
    for role in member.roles:
        if 'mod' in get_role_permissions(ctx.guild.id, role.id).split(','):
            return True
    return False

# Administrative Commands

@bot.command(name="kick", help="Kick a member from the server")
async def kick(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Kick a member from the server."""
    if has_mod_permissions(ctx):
        await member.kick(reason=reason)
        await ctx.send(f"{member} has been kicked. Reason: {reason}")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="ban", help="Ban a member from the server")
async def ban(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Ban a member from the server."""
    if has_mod_permissions(ctx):
        await member.ban(reason=reason)
        await ctx.send(f"{member} has been banned. Reason: {reason}")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="unban", help="Unban a member from the server")
async def unban(ctx: commands.Context, user_id: int):
    """Unban a member from the server using their user ID."""
    if has_mod_permissions(ctx):
        guild = ctx.guild
        try:
            user = await bot.fetch_user(user_id)
            await guild.unban(user)
            await ctx.send(f"{user} has been unbanned.")
        except discord.NotFound:
            await ctx.send("User not found.")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="mute", help="Mute a member in the server")
async def mute(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Mute a member in the server."""
    if has_mod_permissions(ctx):
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            # Create a mute role if it doesn't exist
            mute_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
        await member.add_roles(mute_role, reason=reason)
        await ctx.send(f"{member} has been muted. Reason: {reason}")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="unmute", help="Unmute a member in the server")
async def unmute(ctx: commands.Context, member: discord.Member):
    """Unmute a member in the server."""
    if has_mod_permissions(ctx):
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if mute_role in member.roles:
            await member.remove_roles(mute_role)
            await ctx.send(f"{member} has been unmuted.")
        else:
            await ctx.send(f"{member} is not muted.")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="addrole", help="Add a role to a member")
async def add_role(ctx: commands.Context, member: discord.Member, role: discord.Role):
    """Add a role to a member."""
    if has_mod_permissions(ctx):
        await member.add_roles(role)
        await ctx.send(f"Role {role.name} added to {member}.")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="removerole", help="Remove a role from a member")
async def remove_role(ctx: commands.Context, member: discord.Member, role: discord.Role):
    """Remove a role from a member."""
    if has_mod_permissions(ctx):
        await member.remove_roles(role)
        await ctx.send(f"Role {role.name} removed from {member}.")
    else:
        await ctx.send("You do not have permission to use this command.")

@bot.command(name="setpermissions", help="Set permissions for a role (e.g., 'read,write') or assign 'admin'")
async def set_permissions(ctx: commands.Context, role: discord.Role, *, permissions: str):
    """Set the permissions for a role."""
    if ctx.author.id == ctx.guild.owner_id:
        set_role_permissions(ctx.guild.id, role.id, permissions)
        await ctx.send(f"Permissions for role {role.name} set to: {permissions}")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command(name="getpermissions", help="Get permissions for a role")
async def get_permissions(ctx: commands.Context, role: discord.Role):
    """Get the permissions for a role."""
    if ctx.author.id == ctx.guild.owner_id:
        permissions = get_role_permissions(ctx.guild.id, role.id)
        if permissions:
            await ctx.send(f"Permissions for role {role.name}: {permissions}")
        else:
            await ctx.send(f"No permissions set for role {role.name}")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command(name="checkpermissions", help="Check if a role has a specific permission")
async def check_permissions(ctx: commands.Context, role: discord.Role, permission: str):
    """Check if a role has a specific permission."""
    if ctx.author.id == ctx.guild.owner_id:
        permissions = get_role_permissions(ctx.guild.id, role.id)
        if permission in permissions.split(','):
            await ctx.send(f"Role {role.name} has permission: {permission}")
        else:
            await ctx.send(f"Role {role.name} does not have permission: {permission}")
    else:
        await ctx.send("You are not authorized to use this command.")

@bot.command(name="setinforole", help="Set a role that can use the !info command")
@commands.has_permissions(administrator=True)
async def set_info_role_command(ctx: commands.Context, role: discord.Role):
    """Set a role that can use the !info command."""
    set_info_role(ctx.guild.id, role.id)
    await ctx.send(f"Role {role.name} can now use the !info command.")

@bot.command(name="addinfomember", help="Grant a member permission to use the !info command")
@commands.has_permissions(administrator=True)
async def add_info_member_command(ctx: commands.Context, member: discord.Member):
    """Grant a member permission to use the !info command."""
    add_info_member(ctx.guild.id, member.id)
    await ctx.send(f"Member {member} can now use the !info command.")

@bot.command(name="removeinfomember", help="Revoke a member's permission to use the !info command")
@commands.has_permissions(administrator=True)
async def remove_info_member_command(ctx: commands.Context, member: discord.Member):
    """Revoke a member's permission to use the !info command."""
    remove_info_member(ctx.guild.id, member.id)
    await ctx.send(f"Member {member} can no longer use the !info command.")

@bot.command(name="info", help="Get information about available commands")
async def info(ctx: commands.Context):
    """Provide information about available commands."""
    if is_authorized(ctx):
        info_message = (
            "**God Studio Moderation Bot Commands:**\n"
            "`!kick <member> [reason]`: Kick a member from the server.\n"
            "`!ban <member> [reason]`: Ban a member from the server.\n"
            "`!unban <user_id>`: Unban a member using their user ID.\n"
            "`!mute <member> [reason]`: Mute a member by adding a 'Muted' role.\n"
            "`!unmute <member>`: Unmute a member by removing the 'Muted' role.\n"
            "`!addrole <member> <role>`: Add a role to a member.\n"
            "`!removerole <member> <role>`: Remove a role from a member.\n"
            "`!setpermissions <role> <permissions>`: Set the permissions for a role.\n"
            "`!getpermissions <role>`: Get the permissions for a role.\n"
            "`!checkpermissions <role> <permission>`: Check if a role has a specific permission.\n"
            "`!setinforole <role>`: Set a role that can use the !info command.\n"
            "`!addinfomember <member>`: Grant a member permission to use the !info command.\n"
            "`!removeinfomember <member>`: Revoke a member's permission to use the !info command.\n"
            "`!info`: Get information about available commands."
        )
        await ctx.send(info_message)
    else:
        await ctx.send("You are not authorized to use this command.")

# Event when the bot is ready
@bot.event
async def on_ready() -> None:
    print(f'{bot.user} is now running!')
    init_db()  # Ensure the database is initialized

# Main entry point
def main() -> None:
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
