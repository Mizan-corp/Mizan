# WebAssembly sandbox for compiled community modules (design)

Status: design only. No code, nothing deployed. Written 27 November 2026.
Basis: the user chose WebAssembly for compiled modules (26 Nov) and accepted recommendation 3:
community-written code runs on real workspaces only after this sandbox exists; until then only
no-code modules (manifest + entities + variants + themes) are installable.

## 1. Goal and non-goals

Goal: let a community developer ship logic (a calculation, a validation, a webhook handler, a report
column) inside a `.mzmo` package, and run it on a workspace without trusting the developer.

Non-goals for the first release: UI code (screens stay declarative), background daemons, direct
network or file access, native extensions, any language runtime that needs the host OS.

## 2. Package format

- A compiled module is a `.mzmo` (format 2) with an extra file `code/module.wasm` and a manifest key
  `"code": {"abi": 1, "entry": ["on_event", "compute"], "sha256": "<hash>", "limits": {...}}`.
- The signature already covers every file hash and, since format 2, the package kind. The hash in the
  manifest must equal the file's hash, so swapping the binary breaks the signature.
- Only WASI-free core WebAssembly is accepted. The validator rejects: imports other than the Mizan host
  functions below, start functions, shared memory, threads, more than one memory, and modules over the
  size limit (suggested 2 MB).

## 3. Runtime

- Engine: wasmtime (Apache-2.0, free), run in a separate worker process, never in the web process.
  Python binding `wasmtime`. A crash, trap or timeout kills only the worker call.
- One fresh instance per call. No state survives between calls except what the module writes through
  the host API (section 4). This removes cross-tenant and cross-call leakage.
- Limits per call (defaults, a manifest may ask for less, never more): 50 ms CPU by fuel metering,
  16 MB linear memory, 64 KB input, 256 KB output, 20 host calls. Over a limit: the call is aborted,
  logged, and the module's failure counter goes up. After 5 failures in 10 minutes the module is
  switched off for that workspace and the owner is told.
- Worker runs as an unprivileged user, no network namespace, read-only filesystem, no environment
  secrets. Defence in depth, since the engine itself already gives no OS access.

## 4. Host API (the only imports)

Calls are synchronous and each one is checked against the module's granted scopes.

| Host function | Needs scope | Notes |
| --- | --- | --- |
| `read_record(entity, id)` | the data scope for that entity, e.g. `customers:read` | Tenant-bound: the workspace is fixed by the host, never passed by the module. |
| `query(entity, filter)` | same | Page size capped, filter is the same safe filter language the ERP uses. |
| `write_own(entity, id, fields)` | none beyond owning the entity | Only entities the module declares itself. |
| `emit(event, payload)` | `events:*` for that event | Goes through the existing webhook and event bus. |
| `log(level, text)` | none | Rate limited, size limited, visible to the owner and the developer. |

Not offered at launch: HTTP, time-of-day beyond a host-provided timestamp, randomness beyond a seeded
value, other modules' data without their scope, user passwords or tokens, billing.

## 5. Permissions and install flow

1. Scopes are the same list as today (`framework/manifest.py` `SCOPES`). The install screen shows them
   in plain language. The owner approves or declines; a module never gets a scope the package did not
   declare.
2. Code modules need `"code"` in the manifest plus a signed developer certificate (already required).
3. Mizan reviews every submission by hand at launch (recommendation 4). A reviewed version gets a
   review record bound to the package hash. Install on a real workspace requires that record.
4. Updating a module with new scopes or new code asks the owner again.

## 6. Data safety

- Every host call runs in the tenant's own database session with the same row filters as an ordinary
  request. A module cannot name another workspace.
- Writes go through the normal record service, so audit logs, validation and permissions still apply.
- All calls are logged (module, version, call, duration, result) for the owner and for Mizan.
- Kill switch: Mizan can disable a module version globally; the loader checks it on every call.

## 7. Testing plan

- Unit: validator rejects forbidden imports, start function, oversized memory, hash mismatch.
- Limits: infinite loop traps by fuel, memory growth beyond 16 MB traps, huge output refused.
- Isolation: a module cannot read another tenant's record; a scope-less read is refused.
- Failure counter and auto-disable.
- A small reference module (Rust, compiled to wasm32-unknown-unknown) in the SDK examples, plus the
  SDK command `mizan build-wasm` that wraps compile, hash and package.

## 8. Build order

1. ABI v1 spec and validator (no execution): reject or accept `module.wasm`. Tests.
2. Worker with wasmtime, limits and host API read-only. Tests.
3. `write_own` and `emit`, review record check, failure counter.
4. SDK: example module and build command.
5. Only then: enable install of code modules on real workspaces, behind the manual review gate.

## 9. Open points (to decide with the user before step 5)

- Is a compiled module allowed to be paid later? Free listings only at launch, so not now.
- Maximum size and fuel defaults above are suggestions and need real measurements.
- Whether Python (via a Wasm build) is supported or only Rust/AssemblyScript at first. Suggested:
  Rust and AssemblyScript first.
