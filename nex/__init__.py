"""
MLX-SAGE — personal sage partner on Apple Silicon (package import name: ``nex``).

Primary surface:
- ``nex sage tui`` — local MLX dialogue + living direction
- ``nex we`` — hive cells + joint beneficence
- ``nex supervise`` — Superintendant rails (policy + propellant Grok + WattOS)

Also includes the local multi-model Nex runner (chat, agent, models, serve, MCP)
for mlx-lm / OptiQ-class weights on Apple Silicon.
"""

__version__ = "0.3.0"

# Legacy constant kept for backward compatibility.
# New code should prefer `from nex.models import get_default_model`
DEFAULT_MODEL = "jedisct1/Nex-N2-mini-mlx-OptiQ-4bit"
