import pytest

from shopee_agent.entrypoints.telegram.keyboards import get_pagination_keyboard, get_task_keyboard


def test_task_keyboard_open() -> None:
    markup = get_task_keyboard("t1", "open")
    
    assert len(markup.inline_keyboard) == 2
    assert markup.inline_keyboard[0][0].text == "Ack"
    assert markup.inline_keyboard[0][0].callback_data == "task_ack:t1"
    assert markup.inline_keyboard[0][1].text == "Resolve"
    assert markup.inline_keyboard[0][1].callback_data == "task_resolve:t1"
    assert markup.inline_keyboard[1][0].text == "Dismiss"
    assert markup.inline_keyboard[1][0].callback_data == "task_dismiss:t1"


def test_task_keyboard_acknowledged() -> None:
    markup = get_task_keyboard("t1", "acknowledged")
    
    assert markup.inline_keyboard[0][0].text == "Resolve"
    assert markup.inline_keyboard[0][0].callback_data == "task_resolve:t1"
    assert markup.inline_keyboard[0][1].text == "Waiting"
    assert markup.inline_keyboard[0][1].callback_data == "task_wait:t1"
    assert markup.inline_keyboard[1][0].text == "Dismiss"
    assert markup.inline_keyboard[1][0].callback_data == "task_dismiss:t1"


def test_pagination_keyboard() -> None:
    page_kb = get_pagination_keyboard(page=2, has_next=True)
    assert len(page_kb.inline_keyboard[0]) == 2
    assert page_kb.inline_keyboard[0][0].text == "⬅️ Prev"
    assert page_kb.inline_keyboard[0][0].callback_data == "inbox_page:1"
    assert page_kb.inline_keyboard[0][1].text == "Next ➡️"
    assert page_kb.inline_keyboard[0][1].callback_data == "inbox_page:3"
    
    first_page_kb = get_pagination_keyboard(page=1, has_next=True)
    assert len(first_page_kb.inline_keyboard[0]) == 1
    assert first_page_kb.inline_keyboard[0][0].text == "Next ➡️"
