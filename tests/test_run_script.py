import os
import subprocess
from pathlib import Path


def test_run_script_uses_defaults_without_options_file(tmp_path: Path) -> None:
    fake_bin = tmp_path / "wyoming-doubao-asr"
    fake_bin.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n", encoding="utf-8"
    )
    fake_bin.chmod(0o755)

    env = os.environ.copy()
    env["DATA_DIR"] = str(tmp_path)
    env["WYOMING_DOUBAO_ASR_BIN"] = str(fake_bin)

    result = subprocess.run(
        ["bash", "rootfs/run.sh"],
        cwd=Path(__file__).parent.parent,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--credentials-file\n" in result.stdout
    assert f"{tmp_path}/doubao_credentials.json\n" in result.stdout
    assert "--response-timeout-s\n15\n" in result.stdout
    assert "--zeroconf-timeout-s\n5\n" in result.stdout
    assert "--zeroconf\n" not in result.stdout
    assert "--log-level\nINFO\n" in result.stdout
