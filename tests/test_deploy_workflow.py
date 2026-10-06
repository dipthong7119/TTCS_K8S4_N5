"""T-03: verify deployment failure paths without Docker or a staging server."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def deploy_script():
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8"))
    step = next(item for item in workflow["jobs"]["deploy-staging"]["steps"] if "script" in item.get("with", {}))
    return re.sub(r"\$\{\{[^}]+\}\}", "test", step["with"]["script"])


@pytest.mark.parametrize("scenario", ["success", "bad_candidate", "bad_promotion", "bad_live_health", "bad_pull"])
def test_deploy_preserves_or_restores_previous_image(scenario):
    bash = shutil.which("bash")
    if sys.platform == "win32":
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        if git_bash.is_file():
            bash = str(git_bash)
    if bash is None:
        pytest.skip("Bash is required to validate the staging shell script")
    # Replace every external command that could touch staging, Docker or the
    # network. File descriptor 3 keeps the trace even for redirected commands.
    harness = r'''
exec 3>&1
SCENARIO=SCENARIO_VALUE
ACTIVE_IMAGE=previous
cd() { return 0; }
sleep() { return 0; }
docker() {
  printf 'DOCKER %s IMAGE=%s\n' "$*" "${CSMS_IMAGE:-}" >&3
  if [ "$1" = inspect ]; then printf 'previous\n'; return 0; fi
  if [ "$1" = pull ] && [ "$SCENARIO" = bad_pull ]; then return 1; fi
  case "$*" in
    *'up -d --no-deps app')
      if [ "$SCENARIO" = bad_promotion ] && [ "$CSMS_IMAGE" != previous ]; then return 1; fi
      ACTIVE_IMAGE="$CSMS_IMAGE" ;;
  esac
  return 0
}
curl() {
  printf 'CURL %s\n' "$*" >&3
  if [ "$SCENARIO" = bad_candidate ]; then
    case "$*" in *18000*) return 1 ;; esac
  fi
  if [ "$SCENARIO" = bad_live_health ] && [ "$ACTIVE_IMAGE" != previous ]; then
    case "$*" in *127.0.0.1:8000*) return 1 ;; esac
  fi
  return 0
}
'''.replace("SCENARIO_VALUE", scenario)
    result = subprocess.run([bash, "-s"], input=harness + deploy_script(), text=True, capture_output=True, timeout=15, check=False)
    assert "DOCKER pull" in result.stdout, result.stderr
    promotions = [line for line in result.stdout.splitlines() if "up -d --no-deps app" in line]
    if scenario == "success":
        assert result.returncode == 0, result.stderr
        assert len(promotions) == 1 and "IMAGE=ghcr.io/test/csms-app:test" in promotions[0]
    elif scenario in {"bad_promotion", "bad_live_health"}:
        assert result.returncode != 0
        assert len(promotions) == 2 and promotions[-1].endswith("IMAGE=previous")
    else:
        assert result.returncode != 0
        assert promotions == [], result.stdout
    if scenario != "bad_pull":
        assert "DOCKER rm -f csms_staging_candidate" in result.stdout
    assert "CURL --max-time 3 -fsSL http://127.0.0.1:18000/" in result.stdout or scenario in {"bad_pull", "bad_candidate"}


def test_staging_frontend_comes_from_image_and_local_mount_is_preserved():
    base = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    override = yaml.safe_load((ROOT / "docker-compose.override.yml").read_text(encoding="utf-8"))
    assert not base["services"]["app"].get("volumes")
    assert override["services"]["app"]["volumes"] == ["./frontend:/app/frontend"]
    script = deploy_script()
    assert "docker-compose up" not in script
    assert "docker compose -f docker-compose.yml" in script
