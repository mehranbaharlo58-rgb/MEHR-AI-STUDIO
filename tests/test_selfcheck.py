from mehr_ai_studio.selfcheck import run_self_check


def test_offline_self_check_passes_without_external_services():
    result = run_self_check()
    assert result["ok"] is True
    assert all(result["checks"].values())
    assert result["provider_tested"] is False
    assert result["network_required"] is False
