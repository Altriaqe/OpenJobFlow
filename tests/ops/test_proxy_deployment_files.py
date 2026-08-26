import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROXY_COMPOSE = ROOT / "compose.proxy.yaml"
CONFIG_TEMPLATE = ROOT / "deploy" / "mihomo" / "config.example.yaml"
ENV_EXAMPLE = ROOT / ".env.example"
GITIGNORE = ROOT / ".gitignore"


def service_block(text: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def test_proxy_compose_maps_pinned_mihomo_only_to_host_loopback() -> None:
    text = PROXY_COMPOSE.read_text(encoding="utf-8")
    mihomo = service_block(text, "mihomo")

    assert "metacubex/mihomo:v1.19.30" in mihomo
    assert "restart: unless-stopped" in mihomo
    assert "MIHOMO_CONFIG_DIR" in mihomo
    assert "expose:" in mihomo
    assert '"7890"' in mihomo
    assert "ports:" in mihomo
    assert '"127.0.0.1:${MIHOMO_HOST_PORT:-7890}:7890"' in mihomo
    assert '"0.0.0.0:' not in mihomo


def test_proxy_compose_routes_only_api_runtime_traffic() -> None:
    text = PROXY_COMPOSE.read_text(encoding="utf-8")
    api = service_block(text, "api")

    assert "HTTP_PROXY: http://mihomo:7890" in api
    assert "HTTPS_PROXY: http://mihomo:7890" in api
    assert "NO_PROXY: postgres,mihomo,localhost,127.0.0.1" in api
    assert "condition: service_started" in api
    assert "network: host" in api


def test_proxy_compose_uses_host_network_only_for_app_image_builds() -> None:
    text = PROXY_COMPOSE.read_text(encoding="utf-8")
    etl = service_block(text, "etl")

    assert "network: host" in etl


def test_mihomo_template_contains_only_public_subscription_placeholder() -> None:
    text = CONFIG_TEMPLATE.read_text(encoding="utf-8")

    assert 'url: "<YOUR_PROXY_SUBSCRIPTION_URL>"' in text
    assert "mixed-port: 7890" in text
    assert "allow-lan: true" in text
    assert "MATCH,AUTO" in text


def test_runtime_proxy_files_are_ignored_and_documented() -> None:
    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    gitignore_lines = GITIGNORE.read_text(encoding="utf-8").splitlines()

    assert "MIHOMO_CONFIG_DIR=./runtime/mihomo" in env_text
    assert "MIHOMO_HOST_PORT=7890" in env_text
    assert "JOBFLOW_BUILD_HTTP_PROXY=" in env_text
    assert "JOBFLOW_BUILD_HTTPS_PROXY=" in env_text
    assert "COMPOSE_FILE=compose.yaml:compose.proxy.yaml" in env_text
    assert "runtime/" in gitignore_lines


def test_base_compose_separates_build_and_runtime_proxy_variables() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "HTTP_PROXY: ${JOBFLOW_BUILD_HTTP_PROXY:-}" in text
    assert "HTTPS_PROXY: ${JOBFLOW_BUILD_HTTPS_PROXY:-}" in text
    assert "HTTP_PROXY: ${JOBFLOW_HTTP_PROXY:-}" in text
    assert "HTTPS_PROXY: ${JOBFLOW_HTTPS_PROXY:-}" in text


def test_api_mounts_runtime_for_generated_article_packages() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "./runtime:/app/runtime" in text
