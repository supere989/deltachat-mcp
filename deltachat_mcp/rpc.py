# deltachat_mcp/rpc.py
import asyncio
from deltatachat2 import Rpc, Account
from .config import Config

class DeltaChatRPC:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rpc = Rpc()
            cls._instance.account = Account(cls._instance.rpc, 1)
            cls._instance.loop = asyncio.get_event_loop()
        return cls._instance

    async def ensure_configured(self):
        if not self.account.is_configured():
            await self.account.configure(
                addr=Config.DC_ADDR,
                mail_pw=Config.DC_MAIL_PW,
                basedir=Config.BASEDIR
            )
        if not self.account.is_io_running():
            await self.account.start_io()

    def get_account(self) -> Account:
        return self.account
