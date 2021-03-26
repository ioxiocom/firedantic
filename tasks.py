import re
from pathlib import Path

from invoke import Exit, task

DEV_ENV = {"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8686"}


@task
def release(ctx):
    toml = Path("pyproject.toml").read_text()
    match = re.search(r'version = "(.*?)"', toml)
    if match:
        version = match.group(1)
        print(f"Releasing {version}")
        ctx.run(f"git tag {version}", echo=True)
        ctx.run(f"git push origin {version}", echo=True)
    else:
        print("Failed to find version in the pyproject.toml")


def run_test_cmd(ctx, cmd, env=None) -> int:
    print("=" * 79)
    print(f"> {cmd}")
    return ctx.run(cmd, warn=True, env=env).exited


@task
def test(ctx):
    failed_commands = []

    if run_test_cmd(ctx, "pre-commit run --all-files"):
        failed_commands.append("Pre commit hooks")

    if run_test_cmd(ctx, "mypy firedantic"):
        failed_commands.append("Mypy")

    if run_test_cmd(ctx, "pytest", env=DEV_ENV):
        failed_commands.append("Unit tests")

    if failed_commands:
        msg = "Errors: " + ", ".join(failed_commands)
        raise Exit(message=msg, code=len(failed_commands))


@task
def unasync(ctx):
    """
    Generate source code for synchronous version of library
    """
    import unasync

    unasync.main()
    ctx.run("poetry run black .")
