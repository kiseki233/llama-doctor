"""llama-doctor.

The version tracks the llama.cpp release this build was verified against:
``<upstream version>.<upstream build>``. llama.cpp tags its releases by build
number (``b10731``), so the last segment is the identifier its users recognise.

The tool itself is not tied to that release -- it reads the flag schema from
whichever executable you point it at -- but pinning the number makes the
verified baseline visible at a glance.
"""

__version__ = "0.3.2.10731"

# The build used as ground truth for this release: every flag it reports was
# submitted to this binary and the verdicts compared.
VERIFIED_LLAMA_CPP_VERSION = "0.3.0-dev"
VERIFIED_LLAMA_CPP_BUILD = 10731
