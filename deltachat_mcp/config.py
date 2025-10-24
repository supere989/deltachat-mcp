# deltachat_mcp/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    DC_ADDR = os.getenv("DC_ADDR")
    DC_MAIL_PW = os.getenv("DC_MAIL_PW")
    MCP_MODE = os.getenv("MCP_MODE", "http").lower()  # http or stdio
    MCP_PORT = int(os.getenv("MCP_PORT", "8089"))
    BASEDIR = Path(os.getenv("BASEDIR", "./dc-data")).expanduser()

    @staticmethod
    def validate():
        if not Config.DC_ADDR or not Config.DC_MAIL_PW:
            raise ValueError("DC_ADDR and DC_MAIL_PW must be set in .env")
