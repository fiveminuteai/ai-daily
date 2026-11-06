

def test_cloud_models_switch_turns_off_cloud_providers():
    from fma.llm import providers_from_config
    cfg = {"providers": [{"name": "groq", "base_url": "x", "model": "m", "key_env": "K"},
                         {"name": "ollama", "base_url": "y", "model": "q", "key_env": None, "local": True}],
           "cloud_models": False}
    assert [p.name for p in providers_from_config(cfg)] == ["ollama"]
