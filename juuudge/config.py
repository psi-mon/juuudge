from typing import Optional, Tuple
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
    DEFAULT_DB_FILENAME,
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
    setup_completed: bool = False

def get_config(db: Optional[object] = None) -> Config:
    app_dir = get_app_dir()
    config_file = app_dir / DEFAULT_CONFIG_FILENAME
    cfg = Config()

    # 1. Load from config.toml if present
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

    # 2. Load from DB settings if available
    if db is not None and hasattr(db, "get_provider_config"):
        p_cfg = db.get_provider_config()
        if p_cfg.get("setup_completed"):
            cfg.setup_completed = True
            if p_cfg.get("provider"):
                cfg.llm.provider = p_cfg["provider"]
            if p_cfg.get("api_key"):
                cfg.llm.api_key = p_cfg["api_key"]
            if p_cfg.get("model"):
                cfg.llm.model = p_cfg["model"]
            if p_cfg.get("ollama_host"):
                cfg.llm.ollama_host = p_cfg["ollama_host"]
    elif db is None:
        db_path = app_dir / DEFAULT_DB_FILENAME
        if db_path.exists():
            from juuudge.storage.db import Database
            try:
                local_db = Database(db_path)
                p_cfg = local_db.get_provider_config()
                if p_cfg.get("setup_completed"):
                    cfg.setup_completed = True
                    if p_cfg.get("provider"):
                        cfg.llm.provider = p_cfg["provider"]
                    if p_cfg.get("api_key"):
                        cfg.llm.api_key = p_cfg["api_key"]
                    if p_cfg.get("model"):
                        cfg.llm.model = p_cfg["model"]
                    if p_cfg.get("ollama_host"):
                        cfg.llm.ollama_host = p_cfg["ollama_host"]
            except Exception:
                pass

    # 3. Env override for API key
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    if env_anthropic and not cfg.llm.api_key:
        cfg.llm.api_key = env_anthropic
        cfg.setup_completed = True

    return cfg

def validate_provider_setup(cfg: Config) -> Tuple[bool, str]:
    """Validate whether LLM provider is properly configured before running agent."""
    provider = (cfg.llm.provider or "").lower()
    if provider == "anthropic":
        if not cfg.llm.api_key or not cfg.llm.api_key.strip():
            return (
                False,
                "No Anthropic API key configured. Please run 'juuudge setup' (or Ctrl+S in the TUI) to configure your provider."
            )
        return True, ""
    elif provider in ("ollama", "llama"):
        if not cfg.llm.ollama_host or not cfg.llm.model:
            return (
                False,
                "Ollama host or model is missing. Please run 'juuudge setup' (or Ctrl+S in the TUI) to configure your provider."
            )
        return True, ""
    return (
        False,
        f"Unknown LLM provider '{provider}'. Please run 'juuudge setup' to configure your provider."
    )
