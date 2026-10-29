"""Backward-compatible alias pointing to the live NvidiaNimClient."""
from flakeforge.llm.nim_client import NvidiaNimClient

# Alias existing class name
NebiusTokenFactoryClient = NvidiaNimClient