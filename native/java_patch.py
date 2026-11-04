"""Replace a method in a pinned, checked native source file."""


def replace_method(text, signature, body):
    assert text.count(signature) == 1, signature
    start = text.index("{", text.index(signature))
    end = start + 1
    depth = 1
    while depth:
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
        end += 1
    return text[: start + 1] + "\n" + body + "\n\t" + text[end - 1 :]
