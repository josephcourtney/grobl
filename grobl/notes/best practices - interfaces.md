---
aliases:
  - Best Practices - Interfaces
linter-yaml-title-alias: Best Practices - Interfaces
tags: 
title: Best Practices - Interfaces
---

# Best Practices - Interfaces
## Core Guidelines
### Encapsulate Domain Logic and State
All domain logic, and stateful operations should be located in a submodule, *e.g.* `core/`. It must not depend on interface code. Don't let interface-specific flags, arguments or state leak into the core.

### Treat All Interfaces as APIs
Define clear boundaries and responsibilities for each type of API. Each interface should provide a consistent abstraction over the core functionality, tailored to the idioms of the interface type.
Each interface layer should only consume the core logic and remain unaware of other interfaces. Avoid coupling between interface APIs.

### Interfaces Should Be Thin Wrappers
Interface code should perform as little processing as possible. Limit them to I/O, parsing, formatting, and error reporting. All decision-making and side-effectful behavior should reside in the core.

### Interfaces Should Be Modular
Organize interfaces (e.g., `cli/`, `web/`, `gui/`) in dedicated submodules. Each should import and reuse logic exclusively from `core/`, not from each other.

### Interfaces Should Be Stable
Interfaces should not change unnecessarily. When they must change, use semantic versioning to communicate the presence of changes

## Types of Interface

### Library

The library interface should be optimized for programmatic access.

- Make the public interface explicit using Pythonic ideoms like `__init__.py` and prepending private functions with an underscore
- For the public interface, prioritize stability, type safety, and discoverability
- File organization should mirror the import structure, with possible fine division and re-exporting with `__init__.py`
- Do not use relative imports
- To support Read-Eval-Print Loop (REPL) usage, design objects with introspectable state and helpful `__repr__` strings

### Command Line (CLI)

If appropriate, some or all of a package's functionality may be exposed for direct use from a command line.
> See [[best practices - command line interfaces]] for a more thorough guide.
- Follow idioms appropriate to the type of tool
- Use Entry Points for Interface Integration
  - Declare CLI entry points using the `[project.scripts]` table in `pyproject.toml` to align with PEP 621 conventions:

    ```toml
    [project.scripts]
    mycommand = "mypackage.cli:main"
    ```

### Configuration Files
Configuration including options, paths, and defaults can be managed with static files and environment variables.
- Use a standard, structured config format like TOML or JSON
- If appropriate, publish a schema, and validate against it
- Avoid global state; Parse configuration into an immutable config object and pass it to core logic explicitly.
- As appropriate for the other interface, allow config file options to be overridden, but make precedence rules explicit.

### Web API (HTTP/REST)
Network clients should use a RESTful interface.
- serialization and deserialization should be performed only at the interface boundary
- the interface should be versioned
- all input should be validated
- error messages should be informative

### Graphical User Interface (GUI)
Graphical front-ends should be optimized for interactive use.
- decouple view logic from internal logic
- use controller or presenter layers to adapt core models to GUI components

### Plugin System
Make the library open for extension without required direct modification.
- use a centralized plugin manager with explicit hook specification and declarative registration of plugins
- document expected behavior and use cases
- support a precedence mechanism to enhance plugin composability

### Remote Procedure Call (RPC) API

For structured inter-process communication use a high-performance, standard protocol, *e.g.* gRPC, Thrift, ZeroMQ, etc.
- Define proper service contracts
- Generate client and server stubs from protocol definitions

### Model Context Protocol

For use by language models, make sure that functionality is explained well and appropriate context is supplied.
- Expose functionality with complete explanations of functionality, usage, expectations, and use cases
- Define an explicit JSON schema and use constrained generation if possible
- Avoid implicit global state
  - Include the minimal, interface-relevant subset of state (e.g., `Config`, `Logger`, `UserSession`, `PathHandles`) in responses
