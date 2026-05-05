from pathlib import Path


def test_domain_and_app_modules_do_not_import_provider_frameworks() -> None:
    forbidden = ("from aiogram", "import aiogram", "from fastapi", "import fastapi")
    roots = [Path("src/shopee_agent/app"), Path("src/shopee_agent/contracts")]
    offenders: list[str] = []

    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            for token in forbidden:
                if token in text:
                    offenders.append(f"{path}: {token}")

    assert offenders == []
