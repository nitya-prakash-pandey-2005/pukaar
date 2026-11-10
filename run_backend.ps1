# run from the repo root
if ($env:FAKE -eq "1") { $env:PUKAAR_FAKE = "1" }
uv run python -m uvicorn pukaar.app:create_app --factory --host 127.0.0.1 --port 8766
