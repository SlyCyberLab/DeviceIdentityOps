"""
Core workflow logic: device deployment, onboarding, offboarding, audit writes.

This is deliberately separate from main.py's route handlers - main.py deals
with HTTP, this module deals with "what actually happens" (validate, act,
write to AuditLog). Keeping the safety default (dry-run for device actions)
here rather than at the API boundary is a deliberate choice worth being able
to explain in the interview.

TODO (Phase 5): device deployment logic.
TODO (Phase 6): onboarding/offboarding logic.
"""
