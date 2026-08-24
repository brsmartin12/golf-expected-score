"""The HTTP layer: FastAPI routes wrapping the calculations in `golf`.

Kept as a separate package from `golf` on purpose. The dependency arrow points
one way -- `api` imports `golf`, and `golf` imports nothing from here. That is
what lets the math be tested without a web server, and what would let it be
reused by a CLI, a notebook, or a batch import script later.
"""
