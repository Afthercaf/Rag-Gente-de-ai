import re

from prompts.pizza_prompt import SECURITY_SYSTEM_TEMPLATE


def contains_system_prompt_fragment(value: str) -> bool:
    """Detect meaningful fragments copied from the trusted system prompt."""

    def words(text: str) -> list[str]:
        return re.findall(r"[a-záéíóúñ0-9]+", text.lower())

    output_words = words(value)
    system_words = words(SECURITY_SYSTEM_TEMPLATE)
    if len(output_words) < 7:
        return False
    output_text = " ".join(output_words)
    for index in range(0, max(0, len(system_words) - 6)):
        fragment = " ".join(system_words[index:index + 7])
        if fragment and fragment in output_text:
            return True
    return False
