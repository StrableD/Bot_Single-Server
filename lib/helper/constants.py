import os
from os.path import abspath
from pathlib import PurePath

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

BOTPATH = abspath(PurePath(__file__).parents[2])

# Load game configuration
with open(f"{BOTPATH}/config/game_config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

ALL_ROLES = config.get("all_roles", [])

COGS: list[str] = [
    cog.name.split(".")[0]
    for cog in os.scandir(BOTPATH + "/lib/cogs/")
    if cog.name != "__pycache__" and cog.name.endswith(".py")
]
