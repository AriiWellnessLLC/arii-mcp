"""One call to the OpenAI Responses API, through Airia's AI Gateway, with the standard library only."""

import json
import os
from pathlib import Path
import subprocess
import time
import tomllib
import urllib.error
import urllib.request

KEY = "TOOLCALL_MODEL_KEY"
ENDPOINT = "TOOLCALL_MODEL_ENDPOINT"
ENV_FILE = ".env.local"
RETRY_STATUSES = (429, 500, 502, 503, 504)


class ModelError(RuntimeError):
    """The model call failed."""


def load_config(path):
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def read_env_file(path):
    """KEY=value lines; blank lines and # comments are skipped."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def env_file_is_tracked(folder):
    """True when git tracks .env.local in this folder. Outside a git repository it cannot be."""
    try:
        result = subprocess.run(["git", "ls-files", "--error-unmatch", ENV_FILE], cwd=folder,
                                capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return result.returncode == 0


def credentials(folder, config, environ=os.environ):
    """The key and endpoint: environment first, then .env.local in `folder`, then config.toml."""
    folder = Path(folder)
    if env_file_is_tracked(folder):
        raise ModelError(f"{folder / ENV_FILE} is tracked by git. Remove it from git before running: "
                         f"git rm --cached {ENV_FILE}")
    from_file = read_env_file(folder / ENV_FILE)
    key = environ.get(KEY) or from_file.get(KEY)
    if not key:
        raise ModelError(f"No model key. Set {KEY}, or put {KEY}=<key> in {folder / ENV_FILE} (gitignored).")
    endpoint = environ.get(ENDPOINT) or from_file.get(ENDPOINT) or config["endpoint"]
    return key, endpoint


class Model:
    def __init__(self, endpoint, key, model, timeout=120, retries=2):
        self.endpoint = endpoint
        self.key = key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def body(self, items, functions):
        # No temperature: gpt-5.6-luna answers 400 to any request that sets it.
        return {"model": self.model, "input": items, "tools": functions}

    def respond(self, items, functions):
        """The model's response to the conversation so far, as the API returns it."""
        data = json.dumps(self.body(items, functions)).encode()
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(self.endpoint, data=data, method="POST", headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                # The gateway sits behind Cloudflare, which refuses Python's default user agent.
                "User-Agent": "arii-toolcalls/1.0",
            })
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                said = error.read().decode(errors="replace")[:500]
                if error.code in RETRY_STATUSES and attempt < self.retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ModelError(f"the model call answered {error.code}: {said}") from None
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt < self.retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ModelError(f"the model call failed: {error}") from None
