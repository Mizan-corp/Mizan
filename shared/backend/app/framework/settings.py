"""Module settings. Per-workspace module settings. Today: ModuleRegistry.get_settings()/save_settings() in loader.py
(`POST /modules/{id}/settings`): a save changes only the keys sent (null resets one to its default), each
checked against the manifest's settings_schema (type boolean / number / string up to 500 / select from its
options; an unknown key or a wrong value is a 422)."""
