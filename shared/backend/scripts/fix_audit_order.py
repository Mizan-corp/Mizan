"""Reorder audit_log to occur before await db.commit() in router.py."""
import re
from pathlib import Path

router_path = Path("/home/ammar/projects/Vendora/backend/app/modules/healthcare_clinic/backend/router.py")
content = router_path.read_text(encoding="utf-8")

# Pattern:
# await db.commit()
# await db.refresh(...) (optional)
# 
# await audit_log(...)
# return ...

# Let's inspect the exact pattern for each endpoint
# Notice:
# await db.commit()
# await db.refresh(X)
# 
# await audit_log(
#     ...
# )
# return ...
# We want:
# await audit_log(
#     ...
# )
# await db.commit()
# await db.refresh(X)
# return ...

pattern = re.compile(
    r'( +)await db\.commit\(\)\n( +(?:await db\.refresh\([^\)]+\)\n)?)\n(\1await audit_log\([\s\S]*?\n\1\)\n)',
    re.MULTILINE
)

def replacer(match):
    indent = match.group(1)
    refresh_part = match.group(2)
    audit_part = match.group(3)
    return f"{audit_part}{indent}await db.commit()\n{refresh_part}"

new_content = pattern.sub(replacer, content)

# Check delete_patient:
# await db.delete(patient)
# await db.commit()
# 
# await audit_log(...)
# return ...
del_pattern = re.compile(
    r'( +)await db\.delete\(patient\)\n\1await db\.commit\(\)\n\n(\1await audit_log\([\s\S]*?\n\1\)\n)',
    re.MULTILINE
)

def del_replacer(match):
    indent = match.group(1)
    audit_part = match.group(2)
    return f"{audit_part}{indent}await db.delete(patient)\n{indent}await db.commit()\n"

new_content = del_pattern.sub(del_replacer, new_content)

router_path.write_text(new_content, encoding="utf-8")
print("Reordering completed successfully!")
