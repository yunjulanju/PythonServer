from history import Turn
from prompt import build_messages


def test_no_context_no_history():
    msgs = build_messages("You are Bob.", None, [], "hi")
    assert msgs == [
        {"role": "system", "content": "You are Bob."},
        {"role": "user", "content": "hi"},
    ]


def test_context_appended_to_system():
    msgs = build_messages("You are Bob.", "Player returned your hammer.", [], "hi")
    assert msgs[0] == {
        "role": "system",
        "content": "You are Bob.\n\nPlayer returned your hammer.",
    }


def test_empty_context_string_ignored():
    msgs = build_messages("You are Bob.", "", [], "hi")
    assert msgs[0] == {"role": "system", "content": "You are Bob."}


def test_history_expanded_in_order():
    history = [Turn("u1", "a1"), Turn("u2", "a2")]
    msgs = build_messages("sys", None, history, "u3")
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
    ]
