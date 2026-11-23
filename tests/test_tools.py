from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from deltachat2 import SpecialContactId

from deltachat_mcp.tools import ToolInputError, send_message


def send_rpc():
    rpc = Mock()
    rpc.check_email_validity.return_value = True
    rpc.lookup_contact_id_by_addr.return_value = None
    rpc.get_contacts.return_value = []
    rpc.get_blocked_contacts.return_value = []
    rpc.get_config.return_value = "1"
    rpc.create_contact.return_value = 4
    rpc.create_chat_by_contact_id.return_value = 7
    rpc.misc_send_text_message.return_value = 17
    return rpc


def contact(contact_id, address="test@example.com", *, key=True, available=True, blocked=False):
    return SimpleNamespace(
        id=contact_id, address=address, is_key_contact=key,
        e2ee_avail=available, is_blocked=blocked,
    )


def test_send_message_validation():
    rpc = Mock()
    with pytest.raises(ToolInputError, match="text is required"):
        send_message(rpc, 2, {"text": ""})
    assert not rpc.mock_calls


@pytest.mark.parametrize("params", [{"chat_id": 7}, {"addr": "  Mailto:TEST@example.com  "}])
def test_send_operation_uses_account_and_chat_ids(params):
    rpc = send_rpc()
    rpc.get_config.return_value = "0"

    result = send_message(rpc, 2, {**params, "text": "test message"})

    if "addr" in params:
        rpc.get_config.assert_called_once_with(2, "force_encryption")
        rpc.create_contact.assert_called_once_with(2, "test@example.com", None)
        rpc.create_chat_by_contact_id.assert_called_once_with(2, 4)
    else:
        rpc.get_contacts.assert_not_called()
        rpc.create_contact.assert_not_called()
        rpc.create_chat_by_contact_id.assert_not_called()
    rpc.misc_send_text_message.assert_called_once_with(2, 7, "test message")
    assert result == {"message_id": 17, "chat_id": 7, "text": "test message"}


def test_address_prefers_exact_usable_key_over_plaintext_and_inexact_matches():
    rpc = send_rpc()
    rpc.lookup_contact_id_by_addr.return_value = 11
    rpc.get_contacts.return_value = [
        contact(11, key=False, available=False),
        contact(12, "not-test@example.com"),
        contact(13),
    ]

    result = send_message(rpc, 2, {"addr": "  Mailto:TEST@example.com  ", "text": "test"})

    rpc.get_contacts.assert_called_once_with(2, 0, "test@example.com")
    rpc.get_config.assert_not_called()
    rpc.create_contact.assert_not_called()
    rpc.create_chat_by_contact_id.assert_called_once_with(2, 13)
    rpc.misc_send_text_message.assert_called_once_with(2, 7, "test")
    assert result == {"message_id": 17, "chat_id": 7, "text": "test"}


def test_own_address_uses_saved_messages_under_encryption_policy():
    rpc = send_rpc()
    rpc.lookup_contact_id_by_addr.return_value = SpecialContactId.SELF

    send_message(rpc, 2, {"addr": "  Alias@example.com  ", "text": "private note"})

    rpc.lookup_contact_id_by_addr.assert_called_once_with(2, "alias@example.com")
    rpc.get_contacts.assert_not_called()
    rpc.get_config.assert_not_called()
    rpc.create_contact.assert_not_called()
    rpc.create_chat_by_contact_id.assert_called_once_with(2, SpecialContactId.SELF)
    rpc.misc_send_text_message.assert_called_once_with(2, 7, "private note")


def test_invalid_address_is_rejected_before_contact_lookup():
    rpc = send_rpc()
    rpc.check_email_validity.return_value = False
    with pytest.raises(ToolInputError, match="valid email address"):
        send_message(rpc, 2, {"addr": "not-an-address", "text": "test"})
    rpc.get_contacts.assert_not_called()
    rpc.create_contact.assert_not_called()
    rpc.misc_send_text_message.assert_not_called()


def test_nested_mailto_prefix_cannot_bypass_the_address_checks():
    rpc = send_rpc()
    rpc.get_config.return_value = "0"
    with pytest.raises(ToolInputError, match="valid email address"):
        send_message(rpc, 2, {"addr": "mailto:mailto:test@example.com", "text": "test"})
    rpc.get_contacts.assert_not_called()
    rpc.create_contact.assert_not_called()
    rpc.misc_send_text_message.assert_not_called()


@pytest.mark.parametrize(
    ("contacts", "blocked", "error"),
    [
        ([contact(11), contact(12)], [], "Multiple key contacts"),
        ([contact(11)], [contact(12, blocked=True)], "Multiple key contacts"),
        ([contact(11, available=False)], [], "encryption key is missing"),
        ([], [contact(11, blocked=True)], "is blocked"),
        ([], [contact(11, key=False, blocked=True)], "is blocked"),
    ],
)
def test_unsafe_contact_selection_never_falls_back_to_classic_mail(contacts, blocked, error):
    rpc = send_rpc()
    rpc.get_contacts.return_value = contacts
    rpc.get_blocked_contacts.return_value = blocked
    rpc.get_config.return_value = "0"
    with pytest.raises(ToolInputError, match=error):
        send_message(rpc, 2, {"addr": "test@example.com", "text": "test"})
    rpc.create_contact.assert_not_called()
    rpc.create_chat_by_contact_id.assert_not_called()
    rpc.misc_send_text_message.assert_not_called()


@pytest.mark.parametrize("force_encryption", ["1", None])
def test_address_without_a_key_requires_explicit_classic_mail_policy(force_encryption):
    rpc = send_rpc()
    rpc.get_config.return_value = force_encryption
    with pytest.raises(ToolInputError, match="Scan the contact's SecureJoin QR code"):
        send_message(rpc, 2, {"addr": "test@example.com", "text": "test"})
    rpc.create_contact.assert_not_called()
    rpc.create_chat_by_contact_id.assert_not_called()
    rpc.misc_send_text_message.assert_not_called()
