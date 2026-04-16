def resolve_base_branch(current_branch: str | None, explicit_base: str | None) -> str:
    if explicit_base:
        return explicit_base
    if current_branch:
        return current_branch
    return "main"


def test_explicit_base_wins() -> None:
    assert resolve_base_branch("dev", "release") == "release"


def test_current_branch_is_default_base() -> None:
    assert resolve_base_branch("dev", None) == "dev"


def test_main_is_last_fallback() -> None:
    assert resolve_base_branch(None, None) == "main"
