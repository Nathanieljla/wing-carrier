# Wing Carrier – Package Summary for AI Agents

> **Purpose of this document:** A quick-reference guide for AI agents (and developers) to understand the `wingcarrier` package architecture without re-reading all source files. Read this first before analysing or modifying the codebase.

---

## What Wing Carrier Does

`wingcarrier` is a Python package that enables **live code dispatch** from an IDE to a running DCC application (Maya, Cascadeur, etc.). The workflow is:

1. A developer is editing a `.py` file in their IDE.
2. They trigger a hotkey.
3. Wing Carrier collects the active file's path, resolves its Python module namespace, and sends a command to the target DCC.
4. The DCC **imports or reloads** the module (and calls its `run()` function if present), or executes raw code if the file isn't part of a package.

---

## Repository Layout

```
src/wingcarrier/
├── __init__.py
├── pigeons/                  ← Core library (DCC-agnostic base + per-app subclasses)
│   ├── pigeon.py             ← Abstract base class Pigeon
│   ├── maya.py               ← MayaPigeon
│   ├── cascadeur.py          ← CascadeurPigeon
│   └── __init__.py
└── 3rdparty/                 ← IDE-specific integration layers
    ├── wing/
    │   └── wing_ide_hotkeys/
    │       └── dispatcher.py ← Wing IDE integration (uses wingapi)
    ├── antigravity/
    │   ├── dispatcher.py     ← Antigravity/VS Code integration (uses sys.argv)
    │   └── antigravity_action.md ← Setup guide for the VS Code User Task + keybinding
    └── cascadeur/
        └── wing_cmds/
            └── wing_connect.py ← Cascadeur-side command to connect back to Wing for debugging
```

---

## Core Abstraction: `Pigeon` (`pigeons/pigeon.py`)

All DCC targets subclass `Pigeon`. Key methods agents should know:

| Method | Description |
|---|---|
| `can_dispatch()` | Returns `True` if the target app is reachable right now (e.g. socket is open). **Must override.** |
| `owns_process(process)` | Returns `True` if a given `psutil.Process` belongs to this pigeon's app. Used for debug-attach detection. **Must override.** |
| `send(highlighted_text, module_path, file_path, doc_type)` | Main entry point — sends data to the DCC. **Must override.** |
| `send_python_command(command_string)` | Sends an arbitrary Python string to the DCC. |
| `import_module(module_name, file_path)` | Imports or `importlib.reload()`s a module; falls back to `read_file()` on `ModuleNotFoundError`. Class method. |
| `post_module_import(module)` | Called after a successful import; default behaviour calls `module.run()` if it exists. Class method. |
| `read_file(file_path)` | `exec()`s file contents in `__main__` namespace. Class method. |
| `write_temp_file(txt)` | Writes text to a temp file and returns its path. Used when sending highlighted code. |

**Utility statics** (no override needed): `encode()`, `decode()`, `get_exe_path_from_pid()`, `find_exe_paths_by_name()`, `process_id()`.

---

## Maya Integration (`pigeons/maya.py` → `MayaPigeon`)

- Connects via **TCP socket** on `127.0.0.1:6000` (Maya's `commandPort`).
- `can_dispatch()` — attempts a socket connection; returns `True` if it succeeds.
- `send()` — builds a Python one-liner and sends it over the socket:
  ```python
  import wingcarrier.pigeons; wingcarrier.pigeons.MayaPigeon.receive('<module>', '<doc_type>', '<file_path>')
  ```
- `receive()` (class method, runs **inside Maya**) — calls `import_module()` for Python files, or `read_file()` for non-package / MEL files.
- Supports both **Python** and **MEL** files. MEL support uses `om.MGlobal.executeCommand()`.
- If text is **highlighted**, `module_path` is cleared and the text is written to a temp file first, then sent as an exec rather than an import.

---

## Cascadeur Integration (`pigeons/cascadeur.py` → `CascadeurPigeon`)

Follows the same `Pigeon` contract as `MayaPigeon`. (Refer to `cascadeur.py` for port/protocol specifics.)

Also includes a **Cascadeur-side** command (`3rdparty/cascadeur/wing_cmds/wing_connect.py`) that imports `wingcarrier.wingdbstub` to connect Cascadeur back to Wing IDE as a debug target.

---

## Wing IDE Dispatcher (`3rdparty/wing/wing_ide_hotkeys/dispatcher.py`)

The reference dispatcher implementation. Uses the **`wingapi`** module (Wing IDE's Python API) to:
- Read the active editor's **selected text** and **MIME type** via `wingapi.gApplication.GetActiveEditor()`.
- Read the **active file path** via `editor.GetDocument().GetFilename()`.
- Detect the active **debug session** (attaches `_DEBUG_CARRIER` when a DCC connects to Wing's debugger) via `wingapi.gApplication.GetDebugger()`.

**Key functions:**
| Function | Purpose |
|---|---|
| `_get_module_info()` | Walks parent dirs for `__init__.py` to build the dotted module namespace |
| `_get_document_text()` | Returns `(selected_text, mime_type)` from the active Wing editor |
| `dispatch_carrier(carrier)` | Resolves the target pigeon and calls `carrier.send()` |
| `dispatch_maya()` / `dispatch_cascadeur()` | Convenience wrappers that force a specific pigeon |
| `_find_best_process()` | Iterates `CARRIERS`, returns the first with `can_dispatch() == True` |

**Signal connections** (Wing-specific): the dispatcher hooks `new-runstate` and `current-runstate-changed` on Wing's debugger to auto-set `_DEBUG_CARRIER` when a DCC connects for debugging.

---

## Antigravity / VS Code Dispatcher (`3rdparty/antigravity/dispatcher.py`)

A **CLI-only equivalent** of the Wing dispatcher, created because Antigravity (VS Code) has no Python IDE API. The active file path is passed via `sys.argv[1]` from a VS Code **User Task** using `${file}`.

**Differences from Wing dispatcher:**
| Feature | Wing | Antigravity |
|---|---|---|
| Active file path | `wingapi` editor API | `sys.argv[1]` from VS Code task |
| Selected text | `wingapi` editor API | Not supported (always empty) |
| MIME / doc type | `doc.GetMimeType()` | Inferred from file extension |
| Debug carrier detection | Wing debugger signals | Not applicable |

`_get_module_info()` and `_find_best_carrier()` are functionally identical to the Wing version.

**Setup:** see `antigravity_action.md` — the user adds a global User Task (`Tasks: Open User Tasks`) and a keybinding pointing to this script.

---

## Module Namespace Resolution (`_get_module_info`)

Both dispatchers use the same algorithm. Given `/path/to/mypkg/subpkg/mymodule.py`:
1. Start with `name = "mymodule"`, `path = Path("/path/to/mypkg/subpkg/mymodule.py")`.
2. Check if `path.parent/__init__.py` exists → if yes, prepend `path.parent.name` to `name` and move `path` up.
3. Repeat until no `__init__.py` is found or 20 iterations hit.
4. Strip `.__init__` suffix if the executed file **was** an `__init__.py`.

Result: `"mypkg.subpkg.mymodule"` — used for `importlib.import_module()` / `importlib.reload()`.

---

## Adding a New DCC Target

1. Create `pigeons/<dcc_name>.py` subclassing `Pigeon`.
2. Implement `can_dispatch()`, `owns_process()`, and `send()`.
3. Add an instance to the `CARRIERS` list in **both** dispatcher files:
   - `3rdparty/wing/wing_ide_hotkeys/dispatcher.py`
   - `3rdparty/antigravity/dispatcher.py`
4. Add the corresponding import at the top of each dispatcher.
