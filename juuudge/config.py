from dataclasses import dataclass, field
from pathlib import Path
import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib

from juuudge.constants import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_MAX_TOOL_ROUNDS,
    DEFAULT_TOP_K_RULES,
    DEFAULT_TOP_K_GLOSSARY,
    DEFAULT_EXPAND_HIERARCHICAL_RULES,
    DEFAULT_CONFIG_FILENAME,
)

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
    provider: str = DEFAULT_LLM_PROVIDER
    model: str = DEFAULT_ANTHROPIC_MODEL
    api_key: str = ""
    temperature: float = DEFAULT_TEMPERATURE
    ollama_host: str = DEFAULT_OLLAMA_HOST
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS

@dataclass
class RAGConfig:
    top_k_rules: int = DEFAULT_TOP_K_RULES
    top_k_glossary: int = DEFAULT_TOP_K_GLOSSARY
    expand_hierarchical_rules: bool = DEFAULT_EXPAND_HIERARCHICAL_RULES
    embedder: str = "fastembed"

@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

def get_config() -> Config:
    app_dir = get_app_dir()
    config_file = app_dir / DEFAULT_CONFIG_FILENAME
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
