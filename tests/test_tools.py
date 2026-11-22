from unittest.mock import Mock

import pytest

from deltachat_mcp.tools import ToolInputError, send_message


def test_send_message_validation():
    rpc = Mock()
    with pytest.raises(ToolInputError, match="text is required"):
        send_message(rpc, 2, {"text": ""})
    assert not rpc.mock_calls


@pytest.mark.parametrize("params", [{"chat_id": 7}, {"addr": "test@example.com"}])
def test_send_operation_uses_account_and_chat_ids(params):
    rpc = Mock()
    rpc.create_contact.return_value = 4
    rpc.create_chat_by_contact_id.return_value = 7
    rpc.misc_send_text_message.return_value = 17

    result = send_message(rpc, 2, {**params, "text": "test message"})

    if "addr" in params:
        rpc.create_contact.assert_called_once_with(2, params["addr"], None)
        rpc.create_chat_by_contact_id.assert_called_once_with(2, 4)
    else:
        rpc.create_contact.assert_not_called()
        rpc.create_chat_by_contact_id.assert_not_called()
    rpc.misc_send_text_message.assert_called_once_with(2, 7, "test message")
    assert result == {"message_id": 17, "chat_id": 7, "text": "test message"}
