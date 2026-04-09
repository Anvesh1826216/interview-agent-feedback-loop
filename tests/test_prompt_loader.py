class FakePromptLoader:
    def get_active_prompts(self, db=None):
        return {
            "version": "v1",
            "evaluation_prompt": "You are an evaluator.",
            "clarification_rule": "Ask one clarification.",
        }
        
def test_prompt_loader_reads_active_version():
    loader = FakePromptLoader()
    prompts = loader.get_active_prompts()
    
    assert prompts["version"] == "v1"
    
def test_prompt_loader_returns_prompt_data():
    loader = FakePromptLoader()
    prompts = loader.get_active_prompts()
    
    assert prompts["version"] == "v1"
    assert "evaluation_prompt" in prompts
    assert "clarification_rule" in prompts
    
