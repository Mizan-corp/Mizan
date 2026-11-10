"""Tuition fees and installments: database models.

Standard (docs/MODULE_STANDARD.md): every table belongs to a workspace (a TenantScoped model:
tenant_id is filtered and stamped automatically, and row-level security guards it); table names
start with the module id; money is Numeric, never float; records that matter are archived, not
deleted. None yet.
"""
