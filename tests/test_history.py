from history import Turn, InMemoryHistoryStore


def test_append_and_get():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("hi", "hello"))
    turns = store.get("p1", "n1")
    assert turns == [Turn("hi", "hello")]


def test_get_empty_returns_empty_list():
    store = InMemoryHistoryStore(max_turns=10)
    assert store.get("p1", "n1") == []


def test_sliding_window_trims_oldest():
    store = InMemoryHistoryStore(max_turns=2)
    store.append("p1", "n1", Turn("u1", "a1"))
    store.append("p1", "n1", Turn("u2", "a2"))
    store.append("p1", "n1", Turn("u3", "a3"))
    assert store.get("p1", "n1") == [Turn("u2", "a2"), Turn("u3", "a3")]


def test_keys_are_isolated():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    assert store.get("p1", "n2") == []
    assert store.get("p2", "n1") == []


def test_reset_clears_only_that_key():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    store.append("p1", "n2", Turn("u2", "a2"))
    store.reset("p1", "n1")
    assert store.get("p1", "n1") == []
    assert store.get("p1", "n2") == [Turn("u2", "a2")]


def test_get_returns_copy_not_internal_list():
    store = InMemoryHistoryStore(max_turns=10)
    store.append("p1", "n1", Turn("u", "a"))
    turns = store.get("p1", "n1")
    turns.append(Turn("x", "y"))
    assert store.get("p1", "n1") == [Turn("u", "a")]
