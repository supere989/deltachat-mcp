import pytest
from deltachat_mcp.tools import send_message

@pytest.mark.asyncio
async def test_send_message_validation():
    with pytest.raises(ValueError):
        await send_message({"text": ""})
