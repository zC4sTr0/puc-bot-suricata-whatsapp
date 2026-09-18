from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_runtime_entrypoint_and_packaging_contract_are_explicit():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "suricata.yml").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["python3", "-m", "suricata"]' in dockerfile
    assert 'COPY suricata/whatsapp/package.json suricata/whatsapp/package-lock.json' in dockerfile
    assert 'python -m pytest -q suricata/tests' in workflow
    assert 'node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs' in workflow
    assert 'suricata.entrypoint:main' in pyproject


def test_clean_architecture_contract_keeps_node_as_named_transport_boundary():
    bridge = (ROOT / "suricata" / "bridge.py").read_text(encoding="utf-8")
    node_entrypoint = ROOT / "suricata" / "whatsapp" / "enviar.mjs"

    assert '"enviar.mjs"' in bridge
    assert node_entrypoint.exists()
    assert (ROOT / "docs" / "CONTRACTS.md").exists()
