import re
from pathlib import Path
from time import sleep

from invoke import Exit, task
from watchdog.observers import Observer

DEV_ENV = {"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8686"}
SKIP_WATCH = [".idea", ".pytest_cache", "__pycache__"]


class TestWatcher:
    def __init__(self, ctx):
        self.ctx = ctx

    def dispatch(self, event):
        # Ignore unwanted events
        for skip in SKIP_WATCH:
            if skip in event.src_path:
                return

        if event.is_directory or event.src_path[-1] == "~":
            return

        print(f"{event.src_path} {event.event_type}")

        self.run_tests()

    def run_tests(self):
        result = run_test_cmd(self.ctx, "pytest", env=DEV_ENV)
        if result:
            print("Tests failed. Check output for details.")


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
def watch_tests(ctx):
    handler = TestWatcher(ctx)
    path = str(Path(".").absolute())
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()

    print("Running tests")
    handler.run_tests()

    print(f"Watching {path} for changes.")

    try:
        while True:
            sleep(1)
    finally:
        observer.stop()
        observer.join()


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
