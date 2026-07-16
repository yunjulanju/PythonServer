from history import Turn


def build_messages(
    system_prompt: str,
    context: str | None,
    history: list[Turn],
    message: str,
) -> list[dict]:
    system_content = system_prompt
    if context:
        system_content = f"{system_prompt}\n\n{context}"

    messages: list[dict] = [{"role": "system", "content": system_content}]
    for turn in history:
        messages.append({"role": "user", "content": turn.user})
        messages.append({"role": "assistant", "content": turn.assistant})
    messages.append({"role": "user", "content": message})
    return messages
