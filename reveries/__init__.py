"""reveries – kleine, sarkastische Eigenheiten für deterministische Antworten.

    from reveries import load, apply
    QUIRKS = load("/config/reveries/quirks")
    text = apply(plain, facts={"kiste": 4}, project="nestegg", texts=[frage], quirks=QUIRKS)
"""

from .core import Outcome, apply, build_prompt, explain
from .loader import check, load, load_persona
from .matcher import find, normalize
from .quirk import Quirk

__version__ = "0.1.0"
__all__ = ["load", "find", "apply", "explain", "check", "load_persona", "normalize",
           "build_prompt", "Quirk", "Outcome"]
