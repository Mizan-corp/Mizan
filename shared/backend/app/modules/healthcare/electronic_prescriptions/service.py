"""Electronic prescriptions: business logic.

Functions take the database session and plain values, do one business operation in one
transaction, and raise HTTPException with an Arabic message for the user. Routers and other
modules call these; they never reach into another module's tables. None yet.
"""
