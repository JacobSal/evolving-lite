"""Autonomous-session infrastructure (DEFAULT-OFF).

The autonomy layer is present but not trigger-registered: enabling unsupervised
operation is an explicit, documented opt-in. The only piece shipped in the
loop-closure phase is the single-session lease (lease.py), read by the
forced-verify Stop-gate hook to decide whether to enforce (autonomous session)
or merely observe (interactive session - the default).
"""
