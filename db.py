import aiosqlite 
DATABASE_PATH = "database.db"


async def get_config(server_id):
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT * FROM config WHERE guild_id = ?", (server_id,))
                config = await cursor.fetchone()

                if config is None:
                    return None

                return {
                    'guild_id': config[0],
                    'manager_role_id': config[1],
                    'assistant_manager_role_id': config[2],
                    'channel_id': config[3],
                    'roster': config[4]
                }
    except Exception as e:
        print(f"Error retrieving config: {e}")
        return None

async def get_teams(server_id):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT roleid, emoji FROM teams WHERE server_id = ?", (server_id,))
            result = await cursor.fetchall()
            return result


async def check_table_exists():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config'")
            table = await cursor.fetchone()
            return table is not None

async def print_table_content():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.cursor() as cursor:
            await cursor.execute("SELECT * FROM config")
            rows = await cursor.fetchall()
            print("Config Table Content:", rows)



