from dataclasses import dataclass, field
from pathlib import Path
import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib

def get_app_dir() -> Path:
    override = os.environ.get("JUUUDGE_DIR")
    if override:
        path = Path(override)
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            path = Path(xdg_data) / "juuudge"
        else:
            path = Path.home() / ".juuudge"
    path.mkdir(parents=True, exist_ok=True)
    return path

@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-3-7-sonnet"
    api_key: str = ""
    temperature: float = 0.0
    ollama_host: str = "http://localhost:11434"
    max_tool_rounds: int = 3

@dataclass
class RAGConfig:
    top_k_rules: int = 5
    top_k_glossary: int = 2
    expand_hierarchical_rules: bool = True
    embedder: str = "fastembed"

@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

def get_config() -> Config:
    app_dir = get_app_dir()
    config_file = app_dir / "config.toml"
    cfg = Config()

    if config_file.exists():
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
            if "llm" in data:
                llm_data = data["llm"]
                cfg.llm.provider = llm_data.get("provider", cfg.llm.provider)
                cfg.llm.model = llm_data.get("model", cfg.llm.model)
                cfg.llm.api_key = llm_data.get("api_key", cfg.llm.api_key)
                cfg.llm.temperature = float(llm_data.get("temperature", cfg.llm.temperature))
                cfg.llm.ollama_host = llm_data.get("ollama_host", cfg.llm.ollama_host)
                cfg.llm.max_tool_rounds = int(llm_data.get("max_tool_rounds", cfg.llm.max_tool_rounds))
            if "rag" in data:
                rag_data = data["rag"]
                cfg.rag.top_k_rules = int(rag_data.get("top_k_rules", cfg.rag.top_k_rules))
                cfg.rag.top_k_glossary = int(rag_data.get("top_k_glossary", cfg.rag.top_k_glossary))
                cfg.rag.expand_hierarchical_rules = bool(rag_data.get("expand_hierarchical_rules", cfg.rag.expand_hierarchical_rules))

    # Env override for API key
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    if env_anthropic and not cfg.llm.api_key:
        cfg.llm.api_key = env_anthropic

    return cfg
