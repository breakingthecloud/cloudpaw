"""This repository is public. It must never carry data that identifies an AWS account, a person or a machine.

Fails (reporting file:line, never the value) on: AWS account IDs (any 12-digit number that is not obviously invented),
AWS resource IDs (i-, sg-, vpc-, subnet-, vol-, ami-...), access keys, private keys, IAM Identity Center (SSO) URLs and
absolute paths of a personal machine. Put your real values in a *.local.env file (ignored by git).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {".git", ".venv", "node_modules", ".cache", "cdk.out", "__pycache__", ".pytest_cache", ".cli", "dist"}
SKIP_FILES = {"uv.lock", "package-lock.json", "pnpm-lock.yaml"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".ts", ".html", ".css", ".js", ".toml", ".yaml", ".yml", ".txt", ".sh", ".svg", ".log", ".env", ".example", ".xml", ".urdf", ".xacro"}

TWELVE = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
RULES = {
    "AWS resource ID": re.compile(r"\b(?:i|sg|vpc|subnet|vol|eni|ami|igw|rtb|nat|acl|snap)-[0-9a-f]{8,17}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "SSO start URL": re.compile(r"[a-z0-9-]+\.awsapps\.com"),
    "personal path": re.compile(r"/Users/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\"),
}


def invented(n: str) -> bool:
    return n == "123456789012" or len(set(n)) == 1


def files():
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or path.name in SKIP_FILES or path.name == "test_repo_hygiene.py":
            continue
        if SKIP_DIRS & set(rel.parts) or ".local." in path.name:
            continue
        if path.suffix in TEXT_SUFFIXES or path.name.startswith(".") and path.suffix == "":
            yield path, rel


def test_the_rules_catch_what_they_should():
    assert invented("123456789012") and invented("111111111111") and not invented("987654321098")
    assert RULES["AWS resource ID"].search("i-0123456789abcdef0") and not RULES["AWS resource ID"].search("multi-agent")
    assert RULES["AWS access key"].search("AKIA" + "ABCDEFGHIJKLMNOP")
    assert RULES["SSO start URL"].search("https://example" + ".awsapps.com/start")
    assert RULES["personal path"].search("/Users/someone/dev") and not RULES["personal path"].search("~/dev")


def test_no_account_or_personal_data_in_the_repo():
    offenders = []
    for path, rel in files():
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if any(not invented(m) for m in TWELVE.findall(line)):
                offenders.append(f"{rel}:{i}  (12-digit number: AWS account ID?)")
            for name, rx in RULES.items():
                if rx.search(line):
                    offenders.append(f"{rel}:{i}  ({name})")
    assert not offenders, "Data that must not be public (use a *.local.env file):\n  " + "\n  ".join(offenders)
